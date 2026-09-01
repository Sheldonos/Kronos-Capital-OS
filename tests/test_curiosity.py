from kcos.curiosity import CuriosityEngine
def test_curiosity_prioritizes_information_value():
    c=CuriosityEngine(); hs=c.generate('BTC',[ ] if False else {'surprises':[{'magnitude':.1,'economic_relevance':1,'confidence_gap':1},{'magnitude':.01,'economic_relevance':1,'confidence_gap':1}]})
    assert hs[0].priority>hs[1].priority
