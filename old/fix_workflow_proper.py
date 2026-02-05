import json

with open('wan_gguf_workflow_improved.json', 'r') as f:
    data = json.load(f)

print("=== FIXING WORKFLOW ===")
print()

nodes = data.get('nodes', [])

for node in nodes:
    nid = node.get('id')
    ntype = node.get('type')
    
    if ntype == 'KSamplerAdvanced':
        widgets = node.get('widgets_values', [])
        print(f"Node {nid} ({node.get('title')}):")
        print(f"  BEFORE: {widgets}")
        
        # KSamplerAdvanced widget order:
        # [add_noise, noise_seed, control_after_generate, steps, cfg, sampler_name, scheduler, 
        #  start_at_step, end_at_step, return_with_leftover_noise]
        
        if nid == 9:  # Primo KSampler (HIGH)
            # add_noise = enable, start_at_step = 0, end_at_step = 1, return_with_leftover_noise = enable
            if len(widgets) >= 10:
                widgets[0] = 'enable'      # add_noise
                widgets[3] = 4             # steps
                widgets[7] = 0             # start_at_step  
                widgets[8] = 1             # end_at_step (ERA 'enable'!)
                widgets[9] = 'enable'      # return_with_leftover_noise
                print(f"  AFTER:  {widgets}")
                print("  Fixed: end_at_step changed from 'enable' to 1")
                
        elif nid == 10:  # Secondo KSampler (LOW)
            # add_noise = disable (riceve rumore dal primo), start_at_step = 1, end_at_step = 4
            if len(widgets) >= 10:
                widgets[0] = 'disable'     # add_noise (TU HAI DETTO: deve restare disable)
                widgets[3] = 4             # steps
                widgets[7] = 1             # start_at_step
                widgets[8] = 4             # end_at_step (ERA 'disable'!)
                widgets[9] = 'disable'     # return_with_leftover_noise
                print(f"  AFTER:  {widgets}")
                print("  Fixed: end_at_step changed from 'disable' to 4")
                print("  Fixed: add_noise = 'disable' (come richiesto)")
        print()

# Salva
with open('wan_gguf_workflow_improved.json', 'w') as f:
    json.dump(data, f, indent=2)

print("=== WORKFLOW SALVATO ===")
print("Fix applicati:")
print("- KSampler 9: end_at_step = 1 (era 'enable')")
print("- KSampler 10: add_noise = 'disable' (come richiesto)")
print("- KSampler 10: end_at_step = 4 (era 'disable')")
print()
print("Questo dovrebbe fixare il blocco dopo il primo KSampler.")
