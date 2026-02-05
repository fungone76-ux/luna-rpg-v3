import json

with open('wan_gguf_workflow_improved.json', 'r') as f:
    data = json.load(f)

print("=== CREAZIONE WORKFLOW SEMPLIFICATO ===")
print()

nodes = data.get('nodes', [])
links = data.get('links', [])

# Il workflow attuale usa 2 KSampler (approccio complesso).
# Creiamo una versione con 1 KSampler solo usando solo il modello LOW.
# Questo è meno "fino" ma molto più stabile.

# Steps:
# 1. Modifica il nodo 9 per usare il modello dal nodo 5 (LOW) invece di 22 (LoRA HIGH)
# 2. Rimuovi la connessione dal nodo 9 al nodo 10
# 3. Collega il nodo 9 direttamente al VAE Decode (nodo 11)
# 4. Disabilita o rimuovi il nodo 10

for node in nodes:
    nid = node.get('id')
    
    if nid == 9:  # KSampler unico
        # Cambia il model input per usare il nodo 5 (LOW) invece di 22
        for inp in node.get('inputs', []):
            if inp.get('name') == 'model':
                # Trova il link attuale e modificalo
                old_link = inp.get('link')
                # Modifica per puntare al nodo 5 (UnetLoaderGGUF LOW)
                # Link 81 va al nodo 22, dobbiamo cambiarlo
                print(f"KSampler 9: cambiare model input da link {old_link} (LoRA 22)")
                print("  -> a nodo 5 (UnetLoaderGGUF LOW)")
        
        # Aumenta gli step per compensare (usiamo 8 step totali)
        widgets = node.get('widgets_values', [])
        if len(widgets) >= 10:
            widgets[3] = 8    # steps = 8
            widgets[7] = 0    # start_at_step = 0
            widgets[8] = 8    # end_at_step = 8 (tutti gli step)
            widgets[9] = 'disable'  # return_with_leftover_noise = disable
            print(f"  -> Steps cambiati a 8 totali")

print()
print("Questo approccio richiede modifiche significative ai link.")
print("Alternative più semplice: usare KSamplerAdvanced con singolo modello.")
print()

# Soluzione alternativa: usare solo il modello LOW per entrambi
# Ma mantenere 2 KSampler con meno step ciascuno per ridurre memoria

print("=== SOLUZIONE ALTERNATIVA: Riduzione step ===")
for node in nodes:
    nid = node.get('id')
    
    if nid == 9:  # Primo KSampler - meno step
        widgets = node.get('widgets_values', [])
        if len(widgets) >= 10:
            widgets[3] = 2    # steps = 2
            widgets[7] = 0    # start_at_step = 0
            widgets[8] = 1    # end_at_step = 1
            print(f"KSampler 9: 1 step (0-1)")
    
    elif nid == 10:  # Secondo KSampler - meno step
        widgets = node.get('widgets_values', [])
        if len(widgets) >= 10:
            widgets[3] = 2    # steps = 2
            widgets[7] = 1    # start_at_step = 1
            widgets[8] = 2    # end_at_step = 2
            widgets[0] = 'disable'  # add_noise = disable
            print(f"KSampler 10: 1 step (1-2)")

# Salva versione ridotta
with open('wan_gguf_workflow_light.json', 'w') as f:
    json.dump(data, f, indent=2)

print()
print("=== WORKFLOW SALVATO ===")
print("File: wan_gguf_workflow_light.json")
print()
print("Questo usa solo 2 step totali invece di 4.")
print("Riduce l'uso di memoria e potrebbe evitare il blocco.")
