class M:
    def packet(self,s):return {'hot':[1],'warm':[2],'institutional':[3]}
class G:
    def neighbors(self,s):return {'B':{'correlation':.5}}
from kcos.context_engine import ContextCompiler
def test_context_is_bounded_packet():
    p=ContextCompiler(M(),G()).compile('A',{'world_version':1,'delta':{'x':1}}, {}, {}, {}); assert p['world_version']==1 and 'B' in p['related_markets']
