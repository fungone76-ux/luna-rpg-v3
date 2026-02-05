import json

with open('wan_gguf_workflow_improved.json', 'r') as f:
    data = json.load(f)

print('=== WORKFLOW ANALYSIS ===')
print(f"Last node id: {data.get('last_node_id')}")
print(f"Total nodes: {len(data.get('nodes', []))}")
print()

nodes = data.get('nodes', [])
for node in nodes:
    nid = node.get('id')
    ntype = node.get('type')
    title = node.get('title', '')
    print(f"Node {nid}: {ntype} - {title}")

print()
print('=== LOOKING FOR PROBLEMATIC NODES ===')
# Cerca nodi che potrebbero causare problemi
problematic = ['FreeMemory', 'FreeGPU', 'UnloadModel', 'MemoryClean', 'EmptyCache']
for node in nodes:
    ntype = node.get('type', '')
    title = node.get('title', '')
    for p in problematic:
        if p.lower() in ntype.lower() or p.lower() in title.lower():
            print(f"WARNING: Found problematic node {node.get('id')}: {ntype} - {title}")

print()
print('=== KSAMPLER NODES ===')
for node in nodes:
    ntype = node.get('type', '')
    if 'KSampler' in ntype:
        print(f"KSampler: Node {node.get('id')} - {node.get('title')}")
        print(f"  widgets_values: {node.get('widgets_values')}")

print()
print('=== VIDEO SAVE NODE ===')
for node in nodes:
    ntype = node.get('type', '')
    if any(x in ntype for x in ['SaveAnimated', 'VHS_SaveVideo', 'VideoCombine', 'SaveVideo']):
        print(f"Video node: Node {node.get('id')} - {ntype} - {node.get('title')}")
        print(f"  widgets_values: {node.get('widgets_values')}")
