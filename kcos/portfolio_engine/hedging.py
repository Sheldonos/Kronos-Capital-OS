class HedgePlanner:
    def recommend(self,exposures,threshold=.35):
        total=exposures.get('gross',0) or 1; out=[]
        for k,v in exposures.get('by_asset_class',{}).items():
            if v/total>threshold: out.append({'asset_class':k,'reason':'concentration','exposure_fraction':v/total})
        return out
