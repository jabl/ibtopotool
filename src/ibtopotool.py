#!/usr/bin/env python2
# -*- mode: python; -*-
# -*- coding: utf-8 -*-
# vim: set fileencoding=utf-8

"""
    ibtopotool, a tool to do things with Infiniband topology.
    Copyright (C) 2013-2016  Janne Blomqvist

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""

import networkx as nx


def speed2weight(speed):
    """Convert an IB speed to an edge weight

    See e.g. https://en.wikipedia.org/wiki/InfiniBand

    """
    ss = speed.split('x')
    nlinks = int(ss[0])
    s1 = ss[1]
    if s1 == 'SDR':
        s = 2
    elif s1 == 'DDR':
        s = 4
    elif s1 == 'QDR':
        s = 8
    elif s1 == 'FDR10':
        s = 10 # ???
    elif s1 == 'FDR':
        s = 13.64
    elif s1 == 'EDR':
        s = 24.24
    elif s1 == 'HDR':
        s = 50 # roughly??
    elif s1 == 'NDR':
        s = 100 # roughly?
    elif s1 == 'XDR':
        s = 250 # the future?
    else:
        raise NotImplementedError('Support for Infiniband speed %s not implemented' % s1)
    return nlinks * s


def parse_ibtopo(topofile, shortlabel):
    """
    Parse an Infiniband topology file as generated by ibnetdiscover.

    Returns: A networkx graph representing the IB network
    """
    g = nx.DiGraph()
    switchidx = 0 # Index switches sequentially
    with open(topofile, 'r') as f:
        inblock = False # Switch or Host (Channel Adapter) block
        for line in f:
            if line.startswith('Switch'):
                inblock = True
                guid = line.split()[2][1:-1]
                i = line.index('#')
                s = line[i:].split('"')
                nodedesc = s[1]
                sid = "s%d" % switchidx
                if shortlabel:
                    label = sid
                else:
                    label = "%s\n%s" % (guid, nodedesc)
                g.add_node(guid, desc=nodedesc, type='Switch', label=label)
                switchidx += 1
            elif line.startswith('Ca'):
                inblock = True
                guid = line.split()[2][1:-1]
                i = line.index('#')
                s = line[i:].split('"')
                nodedesc = s[1].split()[0]
                g.add_node(guid, label=nodedesc, type='Host')
            elif len(line) == 0 or line.isspace():
                inblock = False
            elif inblock:
                ls = line.split()
                destguid = ls[1].split('"')[1]
                w = speed2weight(ls[-1])
                # If the edge already exists, add the weigth to it
                try:
                    g[guid][destguid]['weight'] += w
                    g[guid][destguid]['penwidth'] += 1
                except KeyError:
                    g.add_edge(guid, destguid, weight=w)
                    g[guid][destguid]['penwidth'] = 1
    return g

def gen_dot(graph, out):
    from networkx.drawing.nx_pydot import write_dot
    write_dot(graph, out)

def gen_slurm(g, out):
    """
    g: A networkx graph representing the IB network
    out: Output file-like object
    """
    try:
        import hostlist
    except ImportError:
        print("""To generate a slurm topology.conf, you need to install
python-hostlist, https://pypi.python.org/pypi/python-hostlist""")
        raise
    out.write('# topology.conf generated by ibtopo2dot.py\n')
    for n, nbrs in g.adjacency_iter():
        if g.node[n]['type'] == 'Switch':
            switches = []
            nodes = []
            for nbr in nbrs:
                if g.node[nbr]['type'] == 'Switch':
                    switches.append(g.node[nbr]['label'])
                else:
                    nodename = g.node[nbr]['label']
                    nodes.append(nodename)
            switchstring = ""
            if len(switches) > 0:
                switches.sort()
                switchstring = " Switches=" + hostlist.collect_hostlist(switches)
            nodestr = ''
            if len(nodes) > 0:
                nodes.sort()
                nodestr = " Nodes=" + hostlist.collect_hostlist(nodes)
            out.write('SwitchName=%s%s%s\n' % (g.node[n]['label'],
                                               switchstring, nodestr))


def treeify(g, rootfile):
    """Generate a DAG with roots given in the file rootfile"""
    roots = []
    with open(rootfile, 'r') as f:
        for line in f:
            l = line.strip()
            if l.startswith('#') or len(l) == 0:
                continue
            ii = l.find('#')
            if ii >= 1:
                l = l[:ii].rstrip()
            roots.append(l)

    for root in roots:
        # Mark the roots with color for graphviz
        g.node[root]['fillcolor'] = 'red'
        g.node[root]['style'] = 'filled'
        # Mark the roots as roots for graphviz
        g.node[root]['root'] = 'true'
        g.node[root]['rank'] = 0

    # Calculate distance from roots for all nodes
    for n in g.nodes_iter():
        if n in roots:
            continue
        l = []
        for root in roots:
            l.append(nx.shortest_path_length(g, n, root))
        g.node[n]['rank'] = min(l)

    # Drop all edges that go towards the roots, based on the ranks we
    # just computed
    todel = []
    for n, nbrs in g.adjacency_iter():
        for nbr in nbrs:
            if g.node[n]['rank'] > g.node[nbr]['rank']:
                todel.append((n, nbr))
    g.remove_edges_from(todel)
    return g

def only_switches(g):
    """Filter out nodes that are not switches"""
    return g.subgraph([n for n, attrs in g.node.items() if attrs['type']
                       == 'Switch'])

def relabel_switch_tree(g):
    """If shortlabels and treeify is in effect, relabel switches taking
into account the rank (distance from root(s)) in the tree.

    """
    srl = {} # rank:labelindex dict
    for n in g.nodes_iter():
        if g.node[n]['type'] == 'Switch':
            r = g.node[n]['rank']
            if not r in srl:
                srl[r] = 0
            g.node[n]['label'] = 's%d-%d' % (r, srl[r])
            srl[r] += 1

if __name__ == '__main__':
    from optparse import OptionParser
    import sys
    usage = """%prog [options] ibtopofile

ibtopofile is a file containing the output of 'ibnetdiscover'."""
    parser = OptionParser(usage)
    parser.add_option('-s', '--switches', dest='switches', 
                      action='store_true',
                      help='Include only switch nodes')
    parser.add_option('-o', '--output', dest='output',
                      help='Output file, if omitted stdout')
    parser.add_option('--slurm', dest='slurm', action='store_true',
                      help='Output in slurm topology.conf format. Implies --shortlabels.')
    parser.add_option('-t', '--treeify', dest='treeify',
                      help="Give a file containing GUID's for spine switches")
    parser.add_option('--shortlabels', dest='shortlabels', action='store_true',
                      help='Use short labels for switches')
    (options, args) = parser.parse_args()
    if len(args) == 0:
        parser.print_help()
        sys.exit(1)
    if options.slurm:
        options.shortlabels = True
    graph = parse_ibtopo(args[0], options.shortlabels)
    if options.output:
        out = open(options.output, 'w')
    else:
        out = sys.stdout
    if options.switches:
        graph = only_switches(graph)
    if options.treeify:
        graph = treeify(graph, options.treeify)
        if options.shortlabels:
            relabel_switch_tree(graph)
    if options.slurm:
        gen_slurm(graph, out)
    else:
        gen_dot(graph, out)
