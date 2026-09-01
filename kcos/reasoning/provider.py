import json,httpx
class ReasoningProvider:
    """Optional OpenAI-compatible reasoning endpoint. Receives sanitized bounded context only."""
    def __init__(self,base_url=None,api_key=None,model=None): self.base_url=base_url; self.api_key=api_key; self.model=model
    @property
    def enabled(self): return bool(self.base_url and self.api_key and self.model)
    async def hypotheses(self,context,max_items=3):
        if not self.enabled:return []
        prompt={'task':'Generate falsifiable market hypotheses, each with a counter-hypothesis. Do not propose bypassing risk or validation gates.','context':context,'max_items':max_items,'output_schema':{'hypotheses':[{'statement':'','counter_hypothesis':'','economic_relevance':0.0,'confidence_gap':0.0}]}}
        headers={'Authorization':f'Bearer {self.api_key}','Content-Type':'application/json'}
        body={'model':self.model,'messages':[{'role':'system','content':'You are the research reasoning layer of an autonomous quantitative institution. Be skeptical, falsifiable, and cost-aware.'},{'role':'user','content':json.dumps(prompt,default=str)}],'response_format':{'type':'json_object'}}
        async with httpx.AsyncClient(timeout=30) as c:
            r=await c.post(self.base_url.rstrip('/')+'/chat/completions',headers=headers,json=body); r.raise_for_status(); data=r.json()
        try:return json.loads(data['choices'][0]['message']['content']).get('hypotheses',[])[:max_items]
        except Exception:return []
