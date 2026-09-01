class WalkForward:
    def splits(self,n,train=500,test=100,step=100):
        out=[]; start=0
        while start+train+test<=n:
            out.append((slice(start,start+train),slice(start+train,start+train+test))); start+=step
        return out
