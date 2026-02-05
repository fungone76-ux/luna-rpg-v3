import json
import sys
sys.path.insert(0, '.')

# Simula la conversione che fa video_client.py
with open('wan_gguf_workflow_improved.json', 'r') as f:
    workflow = json.load(f)

print("=== TEST CONVERSIONE WORKFLOW ===")
print()

nodes = workflow.get("nodes", [])
links = workflow.get("links", [])

# Costruisci links_map come fa video_client.py
links_map = {}
for link in links:
    if len(link) >= 5:
        from_node = str(link[1])
        from_slot = link[2]
        to_node = str(link[3])
        to_slot = link[4]
        links_map[(to_node, to_slot)] = (from_node, from_slot)

print(f"Total links: {len(links)}")
print(f"Links map entries: {len(links_map)}")
print()

# Converte come fa video_client.py
prompt_dict = {}
WIDGET_ORDERS = {
    "KSamplerAdvanced": ["add_noise", "noise_seed", "control_after_generate", "steps", "cfg", "sampler_name", "scheduler", "start_at_step", "end_at_step", "return_with_leftover_noise"],
}

for node in nodes:
    node_id = str(node.get("id", ""))
    if not node_id:
        continue
    
    inputs = {}
    widgets_values = node.get("widgets_values")
    is_widgets_list = isinstance(widgets_values, list)
    is_widgets_dict = isinstance(widgets_values, dict)
    
    widget_order = WIDGET_ORDERS.get(node.get("type", ""))
    
    for idx, inp in enumerate(node.get("inputs", [])):
        name = inp.get("name", "")
        if not name:
            continue
        
        wname = inp.get("widget", {}).get("name") if isinstance(inp.get("widget"), dict) else None
        
        link_key = (node_id, idx)
        if link_key in links_map:
            from_node, from_slot = links_map[link_key]
            inputs[name] = [from_node, from_slot]
            continue
        
        val = None
        
        if is_widgets_dict and wname and wname in widgets_values:
            val = widgets_values[wname]
        elif is_widgets_list and wname:
            if widget_order and wname in widget_order:
                widx = widget_order.index(wname)
                if widx < len(widgets_values):
                    val = widgets_values[widx]
            else:
                widget_count = sum(1 for i in range(idx) if node["inputs"][i].get("widget"))
                if widget_count < len(widgets_values):
                    val = widgets_values[widget_count]
        elif "widget" in inp and isinstance(inp["widget"], dict):
            val = inp["widget"].get("value")
        
        if val is not None:
            inputs[name] = val
    
    prompt_dict[node_id] = {
        "inputs": inputs,
        "class_type": node.get("type", ""),
        "_meta": {"title": node.get("title", "")}
    }

# Verifica KSampler specificamente
print("=== KSAMPLER DOPO CONVERSIONE ===")
for nid in ["9", "10"]:
    node = prompt_dict.get(nid)
    if node:
        print(f"\nNode {nid} ({node['_meta']['title']}):")
        inputs = node["inputs"]
        
        # Verifica i valori critici
        critical = ["add_noise", "steps", "start_at_step", "end_at_step", "return_with_leftover_noise"]
        for key in critical:
            val = inputs.get(key, "MISSING")
            print(f"  {key}: {val}")
        
        # Verifica se ci sono problemi
        if inputs.get("end_at_step") == inputs.get("start_at_step"):
            print(f"  WARNING: start_at_step == end_at_step! (0 steps)")
        if inputs.get("steps", 0) <= 0:
            print(f"  WARNING: steps <= 0!")

print()
print("=== TEST COMPLETATO ===")
