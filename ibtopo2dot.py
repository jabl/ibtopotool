#!/usr/bin/env python3

# Generate a graphviz dot file from IB topology

def add_lidpair(graph, srclid, targetlid):
    if srclid in graph:
        if targetlid in graph[srclid]:
            graph[srclid][targetlid] += 1
        else:
            graph[srclid][targetlid] = 1
    else:
        graph[srclid] = {targetlid:1}

def parse_ibtopo(topofile):
    desc = {} # dict with {lid:description} mappings
    # Connectivity graph, nested dict
    # {lid:{target_lid:numlinks,...},...}
    graph = {} 
    with open(topofile, 'r') as f:
        sblock = False # Switch block
        hblock = False # Host (Channel Adapter) block
        for line in f:
            if line.startswith('Switch'):
                sblock = True
                i = line.index('lid')
                s = line[i:].split()
                lid = int(s[1])
                i = line.index('#')
                s = line[i:].split('"')
                nodedesc = s[1]
                desc[lid] = {'type':'Switch', 'desc':nodedesc} 
            elif line.startswith('Ca'):
                hblock = True
                i = line.index('#')
                s = line[i:].split('"')
                nodedesc = s[1]
            elif len(line) == 0 or line.isspace():
                sblock = False
                hblock = False
            elif hblock:
                i = line.index('#')
                s = line[i:].split()
                lid = int(s[2])
                desc[lid] = {'type':'Host', 'desc':nodedesc}
                i = line.rindex('lid')
                s = line[i:].split()
                tlid = int(s[1])
                add_lidpair(graph, lid, tlid)
            elif sblock:
                i = line.index('lid')
                s = line[i:].split()
                tlid = int(s[1])
                add_lidpair(graph, lid, tlid)
    return desc, graph

def gen_dot(graph, desc, switches, out):
    out.write('graph ibtopo {\n//For twopi\nranksep=14;\n')
    for k in desc:
        d = desc[k]['desc']
        if desc[k]['type'] == 'Switch':
            c = 'lightblue'
        else:
            c = 'lightgreen'
        if switches:
            if desc[k]['type'] != 'Switch':
                continue
            nh = 0
            for k2 in graph[k]:
                if desc[k2]['type'] == 'Host':
                    nh += 1
            d += '\\nhosts: %d' % nh
        out.write('l%d [label = "%s", style=filled, fillcolor=%s];\n' 
                  % (k, d, c))
    for k in graph:
        if switches and desc[k]['type'] != 'Switch':
            continue
        for k2 in graph[k]:
            if switches and desc[k2]['type'] != 'Switch':
                continue
            if k2 < k:
                continue # Avoid double counting
            numlinks = graph[k][k2]
            if numlinks == 1:
                out.write('l%d -- l%d [weight=10];\n' % (k, k2))
            else:
                out.write('l%d -- l%d [label="%dx",color=red];\n' % (k, k2, numlinks))
    out.write('}\n')

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
    (options, args) = parser.parse_args()
    desc, graph = parse_ibtopo(args[0])
    if options.output:
        out = open(options.output, 'w')
    else:
        out = sys.stdout
    gen_dot(graph, desc, options.switches, out)
