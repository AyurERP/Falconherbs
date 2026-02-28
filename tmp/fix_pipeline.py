import sys

def main():
    path = "core/content_pipeline.py"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Add import
    if "from core.ai_client import call_ai" not in content:
        content = content.replace(
            "from typing import Optional",
            "from typing import Optional\n\nfrom core.ai_client import call_ai"
        )

    # 1. create_blog_draft
    old_blog_gen = """    # Generate content if AI client available\n    if self.ai_client:\n        try:\n            response = self.ai_client.generate(prompt)\n            if response:"""
    new_blog_gen = """    # Generate content using core.ai_client\n        try:\n            response = call_ai("content", [{"role": "user", "content": prompt}])\n            if response and not response.startswith("AI_ERROR"):"""
    
    # Notice: we simply remove the `if self.ai_client:` branch logic wrapper and adjust indentation
    # Actually, the quickest fix is just replacing `if self.ai_client:` with `if True:` and replacing `self.ai_client.generate()` with `call_ai()`.
    
    content = content.replace("if self.ai_client:", "if True:")
    content = content.replace("response = self.ai_client.generate(prompt)", "response = call_ai('content', [{'role': 'user', 'content': prompt}])")
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
        
    print("Fixed core/content_pipeline.py successfully.")

if __name__ == "__main__":
    main()
