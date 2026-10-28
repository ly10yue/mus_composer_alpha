"""Regenerate the embedded skill's tool reference from the executable allowlist."""
import json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'editor'))
from agent_tools import TOOLS
target=root/'editor/skills/interval-chart-agent/references/tool-schema.json'
target.write_text(json.dumps(TOOLS,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Exported',len(TOOLS),'tools to',target)
