import json
import sys
sys.path.insert(0, '.')

# Simula il patching del video_client.py
with open('wan_gguf_workflow_improved.json', 'r') as f:
    workflow = json.load(f)

print("=== TEST PATCHING ===")
print()

nodes = workflow.get("nodes", [])

# Simula il patching
for node in nodes:
    node_id = str(node.get("id", ""))
    node_type = node.get("type", "")
    
    if node_type == "WanFirstLastFrameToVideo":
        print(f"Node {node_id} (WanFirstLastFrameToVideo):")
        print(f"  BEFORE: {node.get('widgets_values')}")
        
        widgets_values = node.get("widgets_values")
        if isinstance(widgets_values, list) and len(widgets_values) >= 4:
            widgets_values[0] = 512  # width
            widgets_values[1] = 512  # height
            widgets_values[2] = 81   # length
            widgets_values[3] = 1    # batch_size
        elif isinstance(widgets_values, dict):
            widgets_values["width"] = 512
            widgets_values["height"] = 512
            widgets_values["length"] = 81
            widgets_values["batch_size"] = 1
        
        print(f"  AFTER:  {node.get('widgets_values')}")

print()
print("=== FINE TEST ===")
