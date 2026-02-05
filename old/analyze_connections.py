import json

with open('wan_gguf_workflow_improved.json', 'r') as f:
    data = json.load(f)

print("=== ANALYZING NODE CONNECTIONS ===")
print()

nodes = {n.get('id'): n for n in data.get('nodes', [])}
links = data.get('links', [])

# Analizza il nodo 8 (WanFirstLastFrameToVideo)
wan_node = nodes.get(8)
if wan_node:
    print("Node 8 (WanFirstLastFrameToVideo) INPUTS:")
    for inp in wan_node.get('inputs', []):
        print(f"  - {inp.get('name')} ({inp.get('type')}): link={inp.get('link')}")
    print()

# Analizza il nodo 9 (KSampler 9)
ksampler9 = nodes.get(9)
if ksampler9:
    print("Node 9 (KSamplerAdvanced) OUTPUTS:")
    for out in ksampler9.get('outputs', []):
        print(f"  - {out.get('name')} ({out.get('type')}): links={out.get('links')}")
    print()

# Cerca tutti i link che coinvolgono il nodo 9
print("All links involving node 9:")
for link in links:
    if len(link) >= 5:
        link_id, from_node, from_slot, to_node, to_slot = link[0], link[1], link[2], link[3], link[4]
        if from_node == 9 or to_node == 9:
            print(f"  Link {link_id}: Node {from_node} (slot {from_slot}) -> Node {to_node} (slot {to_slot})")

print()

# Cerca tutti i link che coinvolgono il nodo 8
print("All links involving node 8:")
for link in links:
    if len(link) >= 5:
        link_id, from_node, from_slot, to_node, to_slot = link[0], link[1], link[2], link[3], link[4]
        if from_node == 8 or to_node == 8:
            print(f"  Link {link_id}: Node {from_node} (slot {from_slot}) -> Node {to_node} (slot {to_slot})")

print()

# Verifica cosa riceve il nodo 8
print("What node 8 receives:")
for link in links:
    if len(link) >= 5:
        _, from_node, from_slot, to_node, to_slot = link
        if to_node == 8:
            from_node_info = nodes.get(from_node, {})
            print(f"  From Node {from_node} ({from_node_info.get('type')}): slot {from_slot} -> slot {to_slot}")

print()

# Verifica cosa riceve il KSampler 10
print("What KSampler 10 receives:")
for link in links:
    if len(link) >= 5:
        _, from_node, from_slot, to_node, to_slot = link
        if to_node == 10:
            from_node_info = nodes.get(from_node, {})
            print(f"  From Node {from_node} ({from_node_info.get('type')}): slot {from_slot} -> slot {to_slot}")
