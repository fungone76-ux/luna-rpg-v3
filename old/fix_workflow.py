import json

with open('wan_gguf_workflow_improved.json', 'r') as f:
    data = json.load(f)

print("=== FIXING WORKFLOW ===")
print()

nodes = data.get('nodes', [])

# Fix 1: Cambia add_noise del secondo KSampler (nodo 10) da 'disable' a 'enable'
for node in nodes:
    if node.get('id') == 10 and node.get('type') == 'KSamplerAdvanced':
        widgets = node.get('widgets_values', [])
        if len(widgets) >= 1:
            old_val = widgets[0]
            widgets[0] = 'enable'  # add_noise = enable
            print(f"[OK] Fixed KSampler 10: add_noise '{old_val}' -> 'enable'")

# Fix 2: Verifica che i LoRA loader siano correttamente collegati
# (a volte i LoRA non caricati causano blocchi)
for node in nodes:
    if node.get('type') == 'LoraLoaderModelOnly':
        widgets = node.get('widgets_values', [])
        if widgets and len(widgets) >= 1:
            lora_name = widgets[0]
            print(f"  LoRA loader {node.get('id')}: {lora_name}")

# Fix 3: Verifica le connessioni critiche
print()
print("=== CRITICAL CONNECTIONS ===")
links = data.get('links', [])

# Cerca connessioni tra KSampler 9 → WanFirstLastFrameToVideo → KSampler 10
ksampler9_to_wan = None
wan_to_ksampler10 = None

for link in links:
    # link format: [link_id, from_node, from_slot, to_node, to_slot]
    if len(link) >= 5:
        from_node = link[1]
        to_node = link[3]
        
        if from_node == 9 and to_node == 8:
            ksampler9_to_wan = link
            print(f"[OK] KSampler 9 -> WanFirstLastFrameToVideo: {link}")
        if from_node == 8 and to_node == 10:
            wan_to_ksampler10 = link
            print(f"[OK] WanFirstLastFrameToVideo -> KSampler 10: {link}")

if not ksampler9_to_wan:
    print("[ERR] MISSING: KSampler 9 -> WanFirstLastFrameToVideo connection!")
if not wan_to_ksampler10:
    print("[ERR] MISSING: WanFirstLastFrameToVideo -> KSampler 10 connection!")

# Salva il workflow fixato
with open('wan_gguf_workflow_improved.json', 'w') as f:
    json.dump(data, f, indent=2)

print()
print("=== WORKFLOW SAVED ===")
print("Main fix: KSampler 10 add_noise changed from 'disable' to 'enable'")
