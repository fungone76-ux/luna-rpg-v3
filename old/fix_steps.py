import json

with open('wan_gguf_workflow_improved.json', 'r') as f:
    data = json.load(f)

print("=== FIXING KSAMPLER STEPS ===")
print()

nodes = data.get('nodes', [])

for node in nodes:
    nid = node.get('id')
    ntype = node.get('type')
    
    if ntype == 'KSamplerAdvanced':
        widgets = node.get('widgets_values', [])
        
        if nid == 9 and len(widgets) >= 10:  # Primo KSampler
            print(f"Node 9 (KSampler HIGH) BEFORE: {widgets}")
            # start_at_step = 0, end_at_step = 1 (fa 1 step con rumore alto)
            widgets[7] = 0   # start_at_step
            widgets[8] = 1   # end_at_step
            print(f"  AFTER: {widgets}")
            print("  -> Esegue step 0-1 (1 step di sampling)")
            
        elif nid == 10 and len(widgets) >= 10:  # Secondo KSampler
            print(f"Node 10 (KSampler LOW) BEFORE: {widgets}")
            # start_at_step = 1, end_at_step = 4 (fa 3 step con rumore basso)
            widgets[7] = 1   # start_at_step
            widgets[8] = 4   # end_at_step
            print(f"  AFTER: {widgets}")
            print("  -> Esegue step 1-4 (3 step di sampling)")
        print()

# Salva
with open('wan_gguf_workflow_improved.json', 'w') as f:
    json.dump(data, f, indent=2)

print("=== WORKFLOW SALVATO ===")
print()
print("Configurazione finale:")
print("- KSampler 9: steps 0-1 con add_noise='enable'")
print("- KSampler 10: steps 1-4 con add_noise='disable'")
print()
print("Questo permette il flusso corretto di rumore tra i due sampler.")
