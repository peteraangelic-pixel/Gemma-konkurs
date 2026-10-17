ages/vllm/lora/worker_manager.py\", line 307, in add_adapter\n"}
,{"stream_name":"stderr","time":367.353090085,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]     lora = self._load_adapter(lora_request)\n"}
,{"stream_name":"stderr","time":367.353092079,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":367.353094051,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]   File \"/usr/local/lib/python3.12/dist-packages/vllm/lora/worker_manager.py\", line 179, in _load_adapter\n"}
,{"stream_name":"stderr","time":367.3530962,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]     raise LoRAAdapterNotFoundError(\n"}
,{"stream_name":"stderr","time":367.353098294,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949] vllm.exceptions.LoRAAdapterNotFoundError: Loading lora main_lora failed: No adapter found for /kaggle/working/main_lora\n"}
,{"stream_name":"stderr","time":367.353100308,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949] Traceback (most recent call last):\n"}
,{"stream_name":"stderr","time":367.353102249,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]   File \"/usr/local/lib/python3.12/dist-packages/vllm/lora/worker_manager.py\", line 118, in _load_adapter\n"}
,{"stream_name":"stderr","time":367.353104288,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]     peft_helper = PEFTHelper.from_local_dir(\n"}
,{"stream_name":"stderr","time":367.353106223,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]                   ^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":367.353108065,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]   File \"/usr/local/lib/python3.12/dist-packages/vllm/lora/peft_helper.py\", line 108, in from_local_dir\n"}
,{"stream_name":"stderr","time":367.353110144,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]     with open(lora_config_path) as f:\n"}
,{"stream_name":"stderr","time":367.353112056,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]          ^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":367.353113933,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949] FileNotFoundError: [Errno 2] No such file or directory: '/kaggle/working/main_lora/adapter_config.json'\n"}
,{"stream_name":"stderr","time":367.353115927,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949] \n"}
,{"stream_name":"stderr","time":367.353117753,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949] The above exception was the direct cause of the following exception:\n"}
,{"stream_name":"stderr","time":367.353119675,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949] \n"}
,{"stream_name":"stderr","time":367.353121573,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949] Traceback (most recent call last):\n"}
,{"stream_name":"stderr","time":367.353123398,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/executor/multiproc_executor.py\", line 944, in worker_busy_loop\n"}
,{"stream_name":"stderr","time":367.35312552,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]     output = func(*args, **kwargs)\n"}
,{"stream_name":"stderr","time":367.353129065,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]              ^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":367.353131166,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/worker/gpu_worker.py\", line 894, in add_lora\n"}
,{"stream_name":"stderr","time":367.353133205,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]     return self.model_runner.add_lora(lora_request)\n"}
,{"stream_name":"stderr","time":367.353135092,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":367.35313699,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/worker/lora_model_runner_mixin.py\", line 273, in add_lora\n"}
,{"stream_name":"stderr","time":367.353139033,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]     return self.lora_manager.add_adapter(lora_request)\n"}
,{"stream_name":"stderr","time":367.353140891,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":367.353142856,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]   File \"/usr/local/lib/python3.12/dist-packages/vllm/lora/worker_manager.py\", line 307, in add_adapter\n"}
,{"stream_name":"stderr","time":367.353144876,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]     lora = self._load_adapter(lora_request)\n"}
,{"stream_name":"stderr","time":367.353146754,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":367.353148606,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]   File \"/usr/local/lib/python3.12/dist-packages/vllm/lora/worker_manager.py\", line 179, in _load_adapter\n"}
,{"stream_name":"stderr","time":367.353150654,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949]     raise LoRAAdapterNotFoundError(\n"}
,{"stream_name":"stderr","time":367.353153624,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949] vllm.exceptions.LoRAAdapterNotFoundError: Loading lora main_lora failed: No adapter found for /kaggle/working/main_lora\n"}
,{"stream_name":"stderr","time":367.353157011,"data":"(Worker_TP0 pid=631) ERROR 10-17 12:15:11 [multiproc_executor.py:949] \n"}
,{"stream_name":"stderr","time":367.353158799,"data":"(EngineCore pid=470) ERROR 10-17 12:15:11 [core.py:1308] Invocation of add_lora method failed\n"}
,{"stream_name":"stderr","time":367.353160706,"data":"(EngineCore pid=470) ERROR 10-17 12:15:11 [core.py:1308] Traceback (most recent call last):\n"}
,{"stream_name":"stderr","time":367.353162796,"data":"(EngineCore pid=470) ERROR 10-17 12:15:11 [core.py:1308]   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/engine/core.py\", line 1298, in _invoke_utility_method\n"}
,{"stream_name":"stderr","time":367.35316492,"data":"(EngineCore pid=470) ERROR 10-17 12:15:11 [core.py:1308]     result = get_result()\n"}
,{"stream_name":"stderr","time":367.35316675,"data":"(EngineCore pid=470) ERROR 10-17 12:15:11 [core.py:1308]              ^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":367.353168703,"data":"(EngineCore pid=470) ERROR 10-17 12:15:11 [core.py:1308]   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/engine/core.py\", line 1258, in \u003clambda\u003e\n"}
,{"stream_name":"stderr","time":367.353172536,"data":"(EngineCore pid=470) ERROR 10-17 12:15:11 [core.py:1308]     get_result = lambda: (method := getattr(self, method_name)) and method(\n"}
,{"stream_name":"stderr","time":367.35317453,"data":"(EngineCore pid=470) ERROR 10-17 12:15:11 [core.py:1308]                                                                     ^^^^^^^\n"}
,{"stream_name":"stderr","time":367.353176444,"data":"(EngineCore pid=470) ERROR 10-17 12:15:11 [core.py:1308]   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/engine/core.py\", line 707, in add_lora\n"}
,{"stream_name":"stderr","time":367.353178482,"data":"(EngineCore pid=470) ERROR 10-17 12:15:11 [core.py:1308]     return self.model_executor.add_lora(lora_request)\n"}
,{"stream_name":"stderr","time":367.353180368,"data":"(EngineCore pid=470) ERROR 10-17 12:15:11 [core.py:1308]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":367.353182281,"data":"(EngineCore pid=470) ERROR 10-17 12:15:11 [core.py:1308]   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/executor/abstract.py\", line 287, in add_lora\n"}
,{"stream_name":"stderr","time":367.353184339,"data":"(EngineCore pid=470) ERROR 10-17 12:15:11 [core.py:1308]     return all(self.collective_rpc(\"add_lora\", args=(lora_request,)))\n"}
,{"stream_name":"stderr","time":367.35318629,"data":"(EngineCore pid=470) ERROR 10-17 12:15:11 [core.py:1308]                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":367.353188194,"data":"(EngineCore pid=470) ERROR 10-17 12:15:11 [core.py:1308]   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/executor/multiproc_executor.py\", line 397, in collective_rpc\n"}
,{"stream_name":"stderr","time":367.353190224,"data":"(EngineCore pid=470) ERROR 10-17 12:15:11 [core.py:1308]     return aggregate(get_response())\n"}
,{"stream_name":"stderr","time":367.353192046,"data":"(EngineCore pid=470) ERROR 10-17 12:15:11 [core.py:1308]                      ^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":367.353193936,"data":"(EngineCore pid=470) ERROR 10-17 12:15:11 [core.py:1308]   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/executor/multiproc_executor.py\", line 380, in get_response\n"}
,{"stream_name":"stderr","time":367.353195994,"data":"(EngineCore pid=470) ERROR 10-17 12:15:11 [core.py:1308]     raise RuntimeError(\n"}
,{"stream_name":"stderr","time":367.353198109,"data":"(EngineCore pid=470) ERROR 10-17 12:15:11 [core.py:1308] RuntimeError: Worker failed with error 'Loading lora main_lora failed: No adapter found for /kaggle/working/main_lora', please check the stack trace above for the root cause\n"}
,{"stream_name":"stderr","time":367.353200251,"data":"(EngineCore pid=470) INFO 10-17 12:15:11 [core.py:1210] Shutdown initiated (timeout=0)\n"}
,{"stream_name":"stderr","time":367.353202074,"data":"(EngineCore pid=470) INFO 10-17 12:15:11 [core.py:1233] Shutdown complete\n"}
,{"stream_name":"stderr","time":367.353203874,"data":"(Worker_TP0 pid=631) INFO 10-17 12:15:11 [multiproc_executor.py:764] Parent process exited, terminating worker queues\n"}
,{"stream_name":"stderr","time":367.353205734,"data":"(Worker_TP3 pid=634) INFO 10-17 12:15:11 [multiproc_executor.py:859] WorkerProc shutting down.\n"}
,{"stream_name":"stderr","time":367.353207549,"data":"(Worker_TP1 pid=632) INFO 10-17 12:15:11 [multiproc_executor.py:859] WorkerProc shutting down.\n"}
,{"stream_name":"stderr","time":367.353209428,"data":"(Worker_TP2 pid=633) INFO 10-17 12:15:11 [multiproc_executor.py:859] WorkerProc shutting down.\n"}
,{"stream_name":"stderr","time":367.353211273,"data":"(Worker_TP0 pid=631) INFO 10-17 12:15:11 [multiproc_executor.py:859] WorkerProc shutting down.\n"}
,{"stream_name":"stderr","time":367.353213116,"data":"(APIServer pid=149) Traceback (most recent call last):\n"}
,{"stream_name":"stderr","time":367.353216664,"data":"(APIServer pid=149)   File \"/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/openai/models/serving.py\", line 188, in load_lora_adapter\n"}
,{"stream_name":"stderr","time":367.353218773,"data":"(APIServer pid=149)     await self.engine_client.add_lora(lora_request)\n"}
,{"stream_name":"stderr","time":367.353220599,"data":"(APIServer pid=149)   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/engine/async_llm.py\", line 922, in add_lora\n"}
,{"stream_name":"stderr","time":367.353222538,"data":"(APIServer pid=149)     return await self.engine_core.add_lora_async(lora_request)\n"}
,{"stream_name":"stderr","time":367.353224321,"data":"(APIServer pid=149)            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":367.353226207,"data":"(APIServer pid=149)   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/engine/core_client.py\", line 1096, in add_lora_async\n"}
,{"stream_name":"stderr","time":367.353228195,"data":"(APIServer pid=149)     return await self.call_utility_async(\"add_lora\", lora_request)\n"}
,{"stream_name":"stderr","time":367.353230109,"data":"(APIServer pid=149)            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":367.353231941,"data":"(APIServer pid=149)   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/engine/core_client.py\", line 1026, in call_utility_async\n"}
,{"stream_name":"stderr","time":367.353233931,"data":"(APIServer pid=149)     return await self._call_utility_async(method, *args, engine=self.core_engine)\n"}
,{"stream_name":"stderr","time":367.353235923,"data":"(APIServer pid=149)            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":367.353237783,"data":"(APIServer pid=149)   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/engine/core_client.py\", line 1040, in _call_utility_async\n"}
,{"stream_name":"stderr","time":367.353239715,"data":"(APIServer pid=149)     return await future\n"}
,{"stream_name":"stderr","time":367.353241528,"data":"(APIServer pid=149)            ^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":367.35324331,"data":"(APIServer pid=149) Exception: Call to add_lora method failed: Worker failed with error 'Loading lora main_lora failed: No adapter found for /kaggle/working/main_lora', please check the stack trace above for the root cause\n"}
,{"stream_name":"stderr","time":367.353246322,"data":"(APIServer pid=149) \n"}
,{"stream_name":"stderr","time":367.353248051,"data":"(APIServer pid=149) The above exception was the direct cause of the following exception:\n"}
,{"stream_name":"stderr","time":367.353249874,"data":"(APIServer pid=149) \n"}
,{"stream_name":"stderr","time":367.353252036,"data":"(APIServer pid=149) Traceback (most recent call last):\n"}
,{"stream_name":"stderr","time":367.353253858,"data":"(APIServer pid=149)   File \"\u003cfrozen runpy\u003e\", line 198, in _run_module_as_main\n"}
,{"stream_name":"stderr","time":367.353255928,"data":"(APIServer pid=149)   File \"\u003cfrozen runpy\u003e\", line 88, in _run_code\n"}
,{"stream_name":"stderr","time":367.353258091,"data":"(APIServer pid=149)   File \"/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/openai/api_server.py\", line 712, in \u003cmodule\u003e\n"}
,{"stream_name":"stderr","time":367.353260194,"data":"(APIServer pid=149)     uvloop.run(run_server(args))\n"}
,{"stream_name":"stderr","time":367.353261956,"data":"(APIServer pid=149)   File \"/usr/local/lib/python3.12/dist-packages/uvloop/__init__.py\", line 96, in run\n"}
,{"stream_name":"stderr","time":367.353263916,"data":"(APIServer pid=149)     return __asyncio.run(\n"}
,{"stream_name":"stderr","time":367.353267241,"data":"(APIServer pid=149)            ^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":367.353269053,"data":"(APIServer pid=149)   File \"/usr/lib/python3.12/asyncio/runners.py\", line 195, in run\n"}
,{"stream_name":"stderr","time":367.353270946,"data":"(APIServer pid=149)     return runner.run(main)\n"}
,{"stream_name":"stderr","time":367.353272686,"data":"(APIServer pid=149)            ^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":367.353274711,"data":"(APIServer pid=149)   File \"/usr/lib/python3.12/asyncio/runners.py\", line 118, in run\n"}
,{"stream_name":"stderr","time":367.353290888,"data":"(APIServer pid=149)     return self._loop.run_until_complete(task)\n"}
,{"stream_name":"stderr","time":367.353297034,"data":"(APIServer pid=149)            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":367.353300091,"data":"(APIServer pid=149)   File \"uvloop/loop.pyx\", line 1518, in uvloop.loop.Loop.run_until_complete\n"}
,{"stream_name":"stderr","time":367.353303227,"data":"(APIServer pid=149)   File \"/usr/local/lib/python3.12/dist-packages/uvloop/__init__.py\", line 48, in wrapper\n"}
,{"stream_name":"stderr","time":367.353306436,"data":"(APIServer pid=149)     return await main\n"}
,{"stream_name":"stderr","time":367.353309251,"data":"(APIServer pid=149)            ^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":367.353312309,"data":"(APIServer pid=149)   File \"/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/openai/api_server.py\", line 672, in run_server\n"}
,{"stream_name":"stderr","time":367.353316424,"data":"(APIServer pid=149)     await run_server_worker(listen_address, sock, args, **uvicorn_kwargs)\n"}
,{"stream_name":"stderr","time":367.353319576,"data":"(APIServer pid=149)   File \"/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/openai/api_server.py\", line 690, in run_server_worker\n"}
,{"stream_name":"stderr","time":367.353323087,"data":"(APIServer pid=149)     shutdown_task = await build_and_serve(\n"}
,{"stream_name":"stderr","time":367.353325031,"data":"(APIServer pid=149)                     ^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":367.353326785,"data":"(APIServer pid=149)   File \"/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/openai/api_server.py\", line 594, in build_and_serve\n"}
,{"stream_name":"stderr","time":367.353328801,"data":"(APIServer pid=149)     await init_app_state(engine_client, app.state, args, supported_tasks)\n"}
,{"stream_name":"stderr","time":367.353330717,"data":"(APIServer pid=149)   File \"/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/openai/api_server.py\", line 361, in init_app_state\n"}
,{"stream_name":"stderr","time":367.353332702,"data":"(APIServer pid=149)     await state.openai_serving_models.init_static_loras()\n"}
,{"stream_name":"stderr","time":367.353334547,"data":"(APIServer pid=149)   File \"/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/openai/models/serving.py\", line 127, in init_static_loras\n"}
,{"stream_name":"stderr","time":367.353336833,"data":"(APIServer pid=149)     load_result = await self.load_lora_adapter(\n"}
,{"stream_name":"stderr","time":367.353338634,"data":"(APIServer pid=149)                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":367.353340513,"data":"(APIServer pid=149)   File \"/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/openai/models/serving.py\", line 195, in load_lora_adapter\n"}
,{"stream_name":"stderr","time":367.353342467,"data":"(APIServer pid=149)     raise LoRAAdapterNotFoundError(\n"}
,{"stream_name":"stderr","time":367.353344226,"data":"(APIServer pid=149) vllm.exceptions.LoRAAdapterNotFoundError: Loading lora main_lora failed: No adapter found for /kaggle/working/main_lora\n"}
,{"stream_name":"stderr","time":367.353349107,"data":"\n"}
,{"stream_name":"stderr","time":367.353351982,"data":"\n"}
,{"stream_name":"stderr","time":369.640908548,"data":"/usr/local/lib/python3.12/dist-packages/mistune.py:435: SyntaxWarning: invalid escape sequence '\\|'\n"}
,{"stream_name":"stderr","time":369.640929004,"data":"  cells[i][c] = re.sub('\\\\\\\\\\|', '|', cell)\n"}
,{"stream_name":"stderr","time":369.795077022,"data":"/usr/local/lib/python3.12/dist-packages/nbconvert/filters/filter_links.py:36: SyntaxWarning: invalid escape sequence '\\_'\n"}
,{"stream_name":"stderr","time":369.795096593,"data":"  text = re.sub(r'_', '\\_', text) # Escape underscores in display text\n"}
,{"stream_name":"stderr","time":370.504722372,"data":"[NbConvertApp] Converting notebook __notebook__.ipynb to notebook\n"}
,{"stream_name":"stderr","time":370.825768842,"data":"[NbConvertApp] Writing 216025 bytes to __notebook__.ipynb\n"}
,{"stream_name":"stderr","time":373.511442482,"data":"[NbConvertApp] Converting notebook __notebook__.ipynb to html\n"}
,{"stream_name":"stderr","time":374.337821814,"data":"[NbConvertApp] Writing 403493 bytes to __results__.html\n"}
]
