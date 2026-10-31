"""Observation controller through Duck's existing Python action tool.

Unrecognized observations are delegated to the original LLM analyzer. The
controller never receives the game ID, baseline, engine, or scoring function.
"""
import inspect
import os


class ControllerAbstained(Exception):
    """Explicit end of a controller-only local evaluation, not an API error."""


def install(ta,controller_class):
    original=ta.ToolAgent.analyze
    signature=inspect.signature(original)
    def analyze(self,*args,**kwargs):
        bound=signature.bind(self,*args,**kwargs)
        bound.apply_defaults()
        values=bound.arguments
        state_path=values['state_path']
        stop=values.get('should_stop')
        if stop and stop():return ta.AnalyzerTurnResult(step_executed=False)
        self._ensure_session(state_path)
        runtime=str(state_path.resolve())
        if getattr(self,'_template_runtime',None)!=runtime:
            self._template_runtime=runtime
            self._template_controller=controller_class()
            self._template_actions=0
        frame,_=ta.load_runtime_state(state_path)
        valid=ta._normalize_valid_actions(values.get('valid_actions'))
        controls=[6] if 'MOUSE' in valid else []
        action=self._template_controller.act(frame.grid,controls,frame.level)
        if action is None:
            if os.environ.get('ARC3_TEMPLATE_ONLY')=='1':
                callback=getattr(self,'_template_stop_callback',None)
                if callback:
                    callback()
                    self._template_abstained=True
                    return ta.AnalyzerTurnResult(step_executed=False,reasoning='Observation controller abstained')
                raise ControllerAbstained('Controller-only evaluator did not install its stop callback')
            return original(self,*args,**kwargs)
        self._step_env_callback=values.get('step_env')
        self._current_valid_actions=valid
        command={'action':'MOUSE','row':action[2],'col':action[1]}
        result=self._run_python_tool(state_path,{'code':'print(action(['+repr(command)+']))'})
        if result.step_executed:self._template_actions+=1
        return ta.AnalyzerTurnResult(step_executed=result.step_executed,
                                    reasoning='Observation-derived symbolic template action')
    ta.ToolAgent.analyze=analyze
