import pandas as pd
class KronosAdapter:
    def __init__(self,model_name,tokenizer_name,device="cpu",max_context=512):
        self.model_name=model_name; self.tokenizer_name=tokenizer_name
        self.device=device; self.max_context=max_context; self.predictor=None
    def load(self):
        if self.predictor is not None: return
        from model import Kronos,KronosTokenizer,KronosPredictor
        tokenizer=KronosTokenizer.from_pretrained(self.tokenizer_name)
        model=Kronos.from_pretrained(self.model_name)
        self.predictor=KronosPredictor(model,tokenizer,max_context=self.max_context)
    def forecast(self,df,future_timestamps,pred_len,sample_count=5):
        self.load()
        cols=["open","high","low","close"]+[c for c in ("volume","amount") if c in df.columns]
        pred=self.predictor.predict(df=df[cols],x_timestamp=pd.Series(df.index),
                                    y_timestamp=future_timestamps,pred_len=pred_len,
                                    T=0.6,top_p=0.9,sample_count=sample_count)
        last=float(df["close"].iloc[-1]); endpoint=float(pred["close"].iloc[-1])
        return {"expected_return":endpoint/last-1.0,"path":pred["close"].astype(float).tolist()}
