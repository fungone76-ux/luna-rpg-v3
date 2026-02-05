import json

with open('wan_gguf_workflow_improved.json', 'r') as f:
    data = json.load(f)

nodes = {n.get('id'): n for n in data.get('nodes', [])}
links = data.get('links', [])

print("=== WORKFLOW COMPLETO ===")
print(f"Last node id: {data.get('last_node_id')}")
print(f"Last link id: {data.get('last_link_id')}")
print(f"Total nodes: {len(nodes)}")
print(f"Total links: {len(links)}")
print()

# Cerca nodi problematici come FreeMemory, FreeCache, etc.
print("=== RICERCA NODI PROBLEMATICI ===")
problematic_keywords = ['free', 'memory', 'cache', 'unload', 'empty', 'clean']
found_issues = []

for nid, node in nodes.items():
    ntype = node.get('type', '').lower()
    title = node.get('title', '').lower()
    
    for kw in problematic_keywords:
        if kw in ntype or kw in title:
            found_issues.append((nid, node.get('type'), node.get('title')))
            break

if found_issues:
    for nid, ntype, title in found_issues:
        print(f"  Node {nid}: {ntype} - {title}")
else:
    print("  Nessun nodo problematico trovato")

print()

# Analizza WanFirstLastFrameToVideo
print("=== WAN FIRST LAST FRAME TO VIDEO (nodo 8) ===")
wan = nodes.get(8)
if wan:
    print(f"Type: {wan.get('type')}")
    print(f"Title: {wan.get('title')}")
    print("Inputs:")
    for inp in wan.get('inputs', []):
        link = inp.get('link')
        name = inp.get('name')
        inp_type = inp.get('type')
        print(f"  - {name} ({inp_type}): link={link}")
    print("Outputs:")
    for out in wan.get('outputs', []):
        name = out.get('name')
        out_type = out.get('type')
        links_out = out.get('links', [])
        print(f"  - {name} ({out_type}): links={links_out}")

print()

# Analizza KSampler 9 e 10 in dettaglio
print("=== KSAMPLER DETTAGLI ===")
for nid in [9, 10]:
    node = nodes.get(nid)
    if node:
        print(f"\nNode {nid}: {node.get('title')}")
        print(f"  Type: {node.get('type')}")
        print(f"  Widgets: {node.get('widgets_values')}")
        print("  Inputs:")
        for inp in node.get('inputs', []):
            print(f"    - {inp.get('name')} ({inp.get('type')}): link={inp.get('link')}")

print()

# Mappa dei link
print("=== MAPPA LINKS CRITICI ===")
critical_links = []
for link in links:
    if len(link) >= 5:
        link_id, from_node, from_slot, to_node, to_slot = link[0], link[1], link[2], link[3], link[4]
        # Link che coinvolgono nodi critici (8, 9, 10)
        if from_node in [8, 9, 10] or to_node in [8, 9, 10]:
            from_info = nodes.get(from_node, {})
            to_info = nodes.get(to_node, {})
            from_name = f"{from_node}:{from_info.get('type', '?')}"
            to_name = f"{to_node}:{to_info.get('type', '?')}"
            print(f"  Link {link_id}: {from_name}[{from_slot}] -> {to_name}[{to_slot}]")

print()
print("=== FINE ANALISI ===")
