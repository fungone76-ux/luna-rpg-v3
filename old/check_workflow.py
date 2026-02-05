import json

with open('wan_gguf_workflow_improved.json') as f:
    w = json.load(f)

print('Nodi nel workflow:')
for n in sorted(w['nodes'], key=lambda x: x['id']):
    print(f"  {n['id']}: {n['type']}")

print(f"\nTotale nodi: {len(w['nodes'])}")
print(f"Last node id: {w['last_node_id']}")
