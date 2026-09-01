from ..domain import RegimeState
class RegimeModel:
    def classify(self,trend_summary,volatility,liquidity_score=1.0):
        structural=trend_summary.get('structural') or trend_summary.get('swing') or {}
        ret=float(structural.get('return',0)); direction='TREND_UP' if ret>.01 else 'TREND_DOWN' if ret<-.01 else 'RANGE'
        vb='HIGH' if volatility>.03 else 'LOW' if volatility<.008 else 'NORMAL'
        lb='THIN' if liquidity_score<.4 else 'DEEP' if liquidity_score>.8 else 'NORMAL'
        name=f'{direction}_{vb}_{lb}'; conf=min(.95,.55+abs(ret)*4+abs(volatility-.015)*3)
        return RegimeState(name,conf,vb,lb,direction,features={'trend_return':ret,'volatility':volatility,'liquidity':liquidity_score})
