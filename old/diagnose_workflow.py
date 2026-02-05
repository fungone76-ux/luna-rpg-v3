import json

with open('wan_gguf_workflow_improved.json', 'r') as f:
    data = json.load(f)

nodes = {n.get('id'): n for n in data.get('nodes', [])}
links = data.get('links', [])

print("=== DIAGNOSI COMPLETA WORKFLOW ===")
print()

# 1. Verifica UnetLoaderGGUF (nodi 4 e 5)
print("1. CARICAMENTO MODELLI")
for nid in [4, 5]:
    node = nodes.get(nid)
    if node:
        widgets = node.get('widgets_values', [])
        print(f"   UnetLoaderGGUF {nid}: {widgets[0] if widgets else 'N/A'}")

print()

# 2. Verifica KSampler connections
print("2. CONNESSIONI KSAMPLER")
ks9 = nodes.get(9)
ks10 = nodes.get(10)

# KSampler 9 input
print("   KSampler 9 (nodo 9):")
for inp in ks9.get('inputs', []):
    if inp.get('link'):
        print(f"     - {inp.get('name')}: connected (link {inp.get('link')})")
    else:
        print(f"     - {inp.get('name')}: NOT CONNECTED!")

# KSampler 10 input
print("   KSampler 10 (nodo 10):")
for inp in ks10.get('inputs', []):
    if inp.get('link'):
        print(f"     - {inp.get('name')}: connected (link {inp.get('link')})")
    else:
        print(f"     - {inp.get('name')}: NOT CONNECTED!")

print()

# 3. Verifica flusso WanFirstLastFrameToVideo
print("3. NODO WanFirstLastFrameToVideo (nodo 8)")
wan = nodes.get(8)
if wan:
    print("   INPUTS:")
    for inp in wan.get('inputs', []):
        link = inp.get('link')
        if link:
            # Trova sorgente
            for l in links:
                if l[0] == link:
                    from_node = nodes.get(l[1], {})
                    print(f"     - {inp.get('name')}: <- Node {l[1]} ({from_node.get('type')})")
                    break
        else:
            print(f"     - {inp.get('name')}: NOT CONNECTED")
    
    print("   OUTPUTS:")
    for out in wan.get('outputs', []):
        out_links = out.get('links', [])
        print(f"     - {out.get('name')}: -> links {out_links}")

print()

# 4. Verifica configurazione steps
print("4. CONFIGURAZIONE STEPS")
for nid in [9, 10]:
    node = nodes.get(nid)
    if node:
        w = node.get('widgets_values', [])
        if len(w) >= 10:
            steps = w[3]
            start = w[7]
            end = w[8]
            actual_steps = end - start
            print(f"   KSampler {nid}: steps={steps}, start={start}, end={end}")
            print(f"      -> Esegue {actual_steps} step di sampling")
            if actual_steps <= 0:
                print(f"      -> ERRORE: esegue 0 step!")

print()

# 5. Verifica VAE Decode
print("5. VAE DECODE (nodo 11)")
vae = nodes.get(11)
if vae:
    for inp in vae.get('inputs', []):
        link = inp.get('link')
        if link:
            for l in links:
                if l[0] == link:
                    from_node = nodes.get(l[1], {})
                    print(f"   - {inp.get('name')}: <- Node {l[1]} ({from_node.get('type')})")

print()

# 6. Possibili problemi
print("6. POSSIBILI PROBLEMI")
issues = []

# Verifica se KSampler 10 riceve latent da KSampler 9
ks10_inputs = ks10.get('inputs', [])
latent_connected = False
for inp in ks10_inputs:
    if inp.get('name') == 'latent_image' and inp.get('link'):
        for l in links:
            if l[0] == inp.get('link') and l[1] == 9:
                latent_connected = True
                break

if not latent_connected:
    issues.append("KSampler 10 NON riceve latent da KSampler 9!")

# Verifica se WanFirstLastFrameToVideo riceve immagine
wan_inputs = wan.get('inputs', [])
image_connected = False
for inp in wan_inputs:
    if inp.get('name') == 'start_image' and inp.get('link'):
        image_connected = True

if not image_connected:
    issues.append("WanFirstLastFrameToVideo non riceve start_image!")

if not issues:
    print("   Nessun problema ovvio rilevato nella struttura.")
else:
    for issue in issues:
        print(f"   ! {issue}")

print()
print("=== DIAGNOSI COMPLETATA ===")
