# ADAPTACJA do audytu: oryginał to analysis/tests/test_template_transfer.py z gałęzi
# codex/arc-local-lab-v18-20261030. Jedyna zmiana: ścieżka do ft09-initial-grid.json
# (oryginał sięga parents[1]/causal-agent-20261031/, tu pliki leżą obok) i sys.path.
# Reszta ciała testów jest nietknięta — 35 passed.
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from template_transfer import TemplateTransfer,infer_copy_action
from template_hook import install


def observed_grid():
    return np.array(json.loads((Path(__file__).resolve().parent/'ft09-initial-grid.json').read_text()),dtype=np.uint8)


@pytest.mark.parametrize('rotation',range(4))
@pytest.mark.parametrize('seed',range(8))
def test_observed_rule_survives_unseen_color_permutation_and_rotation(rotation,seed):
    original=observed_grid()
    palette=np.random.default_rng(seed).permutation(16).astype(np.uint8)
    a=np.rot90(palette[original],rotation)
    active=np.zeros_like(original,dtype=bool);active[36:58,36:58]=True
    active=np.rot90(active,rotation)
    result=infer_copy_action(a)
    assert result is not None
    action,prediction=result
    _,x,y=action
    assert active[y,x]
    assert int(a[y,x])==int(palette[9])
    assert prediction['expected_color']==int(palette[8])


def test_contradicted_prediction_abstains_instead_of_sending_more_clicks():
    a=observed_grid();agent=TemplateTransfer()
    assert agent.act(a,[6],1) is not None
    assert agent.act(a,[6],1) is None # unchanged observation contradicts predicted effect
    assert agent.mismatches==1
    assert agent.rejected


def test_unstructured_grid_abstains():
    a=np.random.default_rng(723).integers(0,16,size=(64,64),dtype=np.uint8)
    assert infer_copy_action(a) is None
    assert TemplateTransfer().act(a,[1,2,3,4],1) is None


def test_hook_delegates_unsupported_observation_and_isolates_state_paths(tmp_path,monkeypatch):
    monkeypatch.delenv('ARC3_TEMPLATE_ONLY',raising=False)
    class Agent:
        def _ensure_session(self,path):pass
        def analyze(self,state_path,action_num,valid_actions=None,step_env=None):
            return ('original',action_num,valid_actions)
    class Controller:
        created=0
        def __init__(self):Controller.created+=1
        def act(self,*args):return None
    ta=SimpleNamespace(ToolAgent=Agent,
        load_runtime_state=lambda p:(SimpleNamespace(grid=np.zeros((64,64)),level=1),[]),
        _normalize_valid_actions=lambda x:x)
    install(ta,Controller)
    agent=Agent()
    assert agent.analyze(tmp_path/'a.json',7,valid_actions=['MOUSE'])==('original',7,['MOUSE'])
    agent.analyze(tmp_path/'a.json',8,valid_actions=['MOUSE'])
    assert Controller.created==1
    agent.analyze(tmp_path/'b.json',0,valid_actions=['MOUSE'])
    assert Controller.created==2
