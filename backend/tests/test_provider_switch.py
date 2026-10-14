"""Key regressions for urgent routing; synthetic keys and intercepted HTTP only."""
import json
import httpx
import pytest
from app.llm import DemoProvider, OpenAIProvider, OpenRouterProvider, ProviderUnavailable, get_provider, get_speech_provider
from app.settings import settings, Settings


@pytest.mark.parametrize('selection,openai_key,expected',[
    ('auto','synthetic-openai','openai'),
    ('auto','','openrouter'),
    ('openrouter','synthetic-openai','openrouter'),
    ('openai','synthetic-openai','openai'),
])
def test_selection_readiness_and_separate_speech_key(monkeypatch,selection,openai_key,expected):
    monkeypatch.setattr(settings,'app_mode','live')
    monkeypatch.setenv('LLM_PROVIDER',selection)
    monkeypatch.setenv('LEARNING_OS_API_KEY',openai_key)
    monkeypatch.setenv('LLM_MODEL','gpt-4o-mini')
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-router')
    monkeypatch.setenv('OPENROUTER_MODEL','openai/gpt-4o-mini')
    provider=get_provider()
    configured=Settings()
    assert provider.name==configured.llm_provider==expected
    assert provider.key==configured.api_key
    assert provider.model==configured.model
    if openai_key:
        speech=get_speech_provider()
        assert type(speech) is OpenAIProvider and speech.key==openai_key
        monkeypatch.delenv('LLM_MODEL')
        monkeypatch.setenv('LEARNING_OS_MODEL','gpt-4o-mini')
        assert get_speech_provider().model=='gpt-4o-mini'
        assert Settings().model==get_provider().model
        monkeypatch.setenv('LLM_MODEL','gpt-4o-mini')
    else:
        with pytest.raises(ProviderUnavailable):get_speech_provider()
    monkeypatch.setenv('LLM_PROVIDER','openrouter')
    monkeypatch.delenv('OPENROUTER_API_KEY')
    with pytest.raises(ProviderUnavailable):get_provider()
    monkeypatch.setattr(settings,'app_mode','test')
    assert isinstance(get_provider(),DemoProvider)


def test_openrouter_wire_contract_keeps_schema_source_validation_and_key_isolation(monkeypatch):
    monkeypatch.setenv('OPENROUTER_API_KEY','synthetic-router')
    monkeypatch.setenv('LEARNING_OS_API_KEY','synthetic-openai')
    monkeypatch.setenv('OPENROUTER_MODEL','openai/gpt-4o-mini')
    context={'study_locale':'en','mode':'study','concepts':[{'id':'protons','text':'Atomic number is proton count.'}],
        'citations':[{'id':'original','excerpt':'Atomic number is proton count.'}]}
    turn=DemoProvider().generate('turn',context)
    requests=[]
    def handler(request):
        requests.append(request)
        body=json.loads(request.content)
        assert str(request.url)=='https://openrouter.ai/api/v1/chat/completions'
        assert request.headers['authorization']=='Bearer synthetic-router'
        assert body['model']=='openai/gpt-4o-mini'
        assert body['provider']=={'require_parameters':True}
        assert body['response_format']['json_schema']['strict'] is True
        assert body['max_tokens']==4096 and 'max_completion_tokens' not in body
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(turn)}}]})
    client_type=httpx.Client
    monkeypatch.setattr('app.llm.httpx.Client',lambda **kw:client_type(transport=httpx.MockTransport(handler),**kw))
    provider=OpenRouterProvider()
    assert provider.generate('turn',context)==turn
    from app.llm import InvalidModelOutput
    turn['source_quotes'][0]['quote']='Unsupported invented claim'
    with pytest.raises(InvalidModelOutput):provider.generate('turn',context)
    count=len(requests)
    with pytest.raises(ProviderUnavailable):provider._request('realtime/client_secrets',json={})
    assert len(requests)==count
