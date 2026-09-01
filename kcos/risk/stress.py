class StressEngine:
    DEFAULT={'equity_crash':{'EQUITY':-.20,'ETF':-.15,'CRYPTO':-.30},'rates_shock':{'RATE':-.08,'EQUITY':-.08,'CRYPTO':-.12},'crypto_crash':{'CRYPTO':-.45}}
    def run(self,notional_by_asset,scenarios=None):
        out={}
        for name,shocks in (scenarios or self.DEFAULT).items(): out[name]=sum(float(notional_by_asset.get(a,0))*float(shock) for a,shock in shocks.items())
        return out
