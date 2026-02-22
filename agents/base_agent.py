from core.ai_client import call_ai
import json

class BaseAgent:
    """Base class for all intelligent agents"""
    
    def __init__(self, whatsapp_client=None):
        self._whatsapp = whatsapp_client
        self.name = "BaseAgent"
        self.ai_role = "fallback"  # Override in child class
        self.capabilities = []      # Override in child class
    
    def think(self, task: str, context: dict = None) -> dict:
        """Agent thinks about how to approach a task"""
        system_prompt = f"""You are {self.name} of Falcon Agency.

Your capabilities: {', '.join(self.capabilities)}

Analyze the task and respond in JSON:
{{
    "understood": "what you understood",
    "approach": "how you will do it", 
    "steps": ["step1", "step2", ...],
    "tools_needed": ["tool1", "tool2"],
    "estimated_time": "X minutes",
    "confidence": "high|medium|low"
}}
"""
        context_str = json.dumps(context) if context else "None"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task: {task}\nContext: {context_str}"}
        ]
        
        response = call_ai(self.ai_role, messages)
        try:
            return json.loads(response)
        except:
            return {"error": "Parse failed", "raw": response}
    
    def execute(self, action: str, details: str) -> str:
        """Execute a task — override in child class"""
        raise NotImplementedError("Child class must implement execute()")
    
    def report_to_owner(self, message: str, priority: str = "normal"):
        """Direct line to owner"""
        if self._whatsapp:
            prefix = "🚨" if priority == "high" else "📢"
            self._whatsapp.send_message(f"{prefix} [{self.name}]: {message}")
    
    def escalate(self, issue: str):
        """Escalate critical issue to owner"""
        if self._whatsapp:
            self._whatsapp.send_message(f"⚠️ ESCALATION from {self.name}:\n{issue}")
    
    def complain(self, about: str, issue: str):
        """Agent can complain about problems"""
        if self._whatsapp:
            self._whatsapp.send_message(
                f"📝 COMPLAINT from {self.name}:\n"
                f"Regarding: {about}\n"
                f"Issue: {issue}"
            )
