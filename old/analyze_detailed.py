import json

with open('wan_gguf_workflow_improved.json', 'r') as f:
    data = json.load(f)

nodes = {n.get('id'): n for n in data.get('nodes', [])}
links = data.get('links', [])

print("=== FLUSSO DATI KSAMPLER ===")
print()

# KSampler 9 (nodo 9) - cosa riceve?
ks9 = nodes.get(9)
print("KSampler 9 (nodo 9) INPUTS:")
for i, inp in enumerate(ks9.get('inputs', [])):
    link = inp.get('link')
    name = inp.get('name')
    if link:
        # Trova da dove viene
        for l in links:
            if len(l) >= 5 and l[0] == link:
                from_node = nodes.get(l[1], {})
                print(f"  [{i}] {name}: <- Node {l[1]} ({from_node.get('type')}) slot {l[2]}")
    else:
        print(f"  [{i}] {name}: NOT CONNECTED")

print()

# KSampler 10 (nodo 10) - cosa riceve?
ks10 = nodes.get(10)
print("KSampler 10 (nodo 10) INPUTS:")
for i, inp in enumerate(ks10.get('inputs', [])):
    link = inp.get('link')
    name = inp.get('name')
    if link:
        for l in links:
            if len(l) >= 5 and l[0] == link:
                from_node = nodes.get(l[1], {})
                print(f"  [{i}] {name}: <- Node {l[1]} ({from_node.get('type')}) slot {l[2]}")
    else:
        print(f"  [{i}] {name}: NOT CONNECTED")

print()
print("=== ANALISI PROBLEMI ===")

# Verifica: KSampler 10 deve ricevere:
# 1. model (da LoRA loader 22)
# 2. positive (da WanFirstLastFrameToVideo slot 0)
# 3. negative (da WanFirstLastFrameToVideo slot 1)  
# 4. latent_image (da KSampler 9 slot 0 - LINK 69)

# KSampler 9 OUTPUT -> KSampler 10 INPUT
ks9_outputs = ks9.get('outputs', [])
for out in ks9_outputs:
    if out.get('name') == 'LATENT':
        links_from_ks9 = out.get('links', [])
        print(f"KSampler 9 LATENT outputs to links: {links_from_ks9}")
        for l in links:
            if len(l) >= 5 and l[0] in links_from_ks9:
                to_node = nodes.get(l[3], {})
                print(f"  -> Link {l[0]} to Node {l[3]} ({to_node.get('type')}) slot {l[4]}")

print()

# Verifica LoRA connections
print("LoRA Loaders outputs:")
for node_id in [21, 22]:
    node = nodes.get(node_id)
    if node:
        print(f"  LoRA {node_id} ({node.get('widgets_values', ['?'])[0]}):")
        for out in node.get('outputs', []):
            links_from_lora = out.get('links', [])
            print(f"    {out.get('name')} -> links {links_from_lora}")

print()
print("=== WIDGET VALUES CRITICI ===")
print("KSampler 9:")
widgets9 = ks9.get('widgets_values', [])
print(f"  add_noise: {widgets9[0] if len(widgets9) > 0 else 'N/A'}")
print(f"  steps: {widgets9[3] if len(widgets9) > 3 else 'N/A'}")
print(f"  cfg: {widgets9[4] if len(widgets9) > 4 else 'N/A'}")
print(f"  sampler: {widgets9[5] if len(widgets9) > 5 else 'N/A'}")
print(f"  start_at_step: {widgets9[8] if len(widgets9) > 8 else 'N/A'}")
print(f"  end_at_step: {widgets9[9] if len(widgets9) > 9 else 'N/A'}")
print(f"  return_with_leftover_noise: {widgets9[10] if len(widgets9) > 10 else 'N/A'}")

print()
print("KSampler 10:")
widgets10 = ks10.get('widgets_values', [])
print(f"  add_noise: {widgets10[0] if len(widgets10) > 0 else 'N/A'}")
print(f"  steps: {widgets10[3] if len(widgets10) > 3 else 'N/A'}")
print(f"  cfg: {widgets10[4] if len(widgets10) > 4 else 'N/A'}")
print(f"  sampler: {widgets10[5] if len(widgets10) > 5 else 'N/A'}")
print(f"  start_at_step: {widgets10[8] if len(widgets10) > 8 else 'N/A'}")
print(f"  end_at_step: {widgets10[9] if len(widgets10) > 9 else 'N/A'}")
print(f"  return_with_leftover_noise: {widgets10[10] if len(widgets10) > 10 else 'N/A'}")

print()
print("=== NOTE ===")
print("Il flusso corretto dovrebbe essere:")
print("1. KSampler 9 genera frame con steps 0-1 (rumore alto)")
print("2. KSampler 9 restituisce LATENT con rumore residuo")
print("3. WanFirstLastFrameToVideo elabora (ma il latent passa attraverso?)")
print("4. KSampler 10 riceve latent da KSampler 9 via link 69")
print("5. KSampler 10 continua con steps 1-4 (senza aggiungere rumore)")
