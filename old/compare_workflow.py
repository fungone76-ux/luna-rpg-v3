import json

with open('wan_gguf_workflow_improved.json') as f:
    w = json.load(f)

print('NODI:')
for n in sorted(w['nodes'], key=lambda x: x['id']):
    print(f"  {n['id']}: {n['type']}")

print(f"\nLINKS ({len(w['links'])}):")
for l in w['links']:
    print(f"  {l}")
