st recent call last):\n"}
,{"stream_name":"stderr","time":391.867656588,"data":"(Worker pid=759) ERROR 10-17 11:41:28 [multiproc_executor.py:857]   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/executor/multiproc_executor.py\", line 826, in worker_main\n"}
,{"stream_name":"stderr","time":391.867658793,"data":"(Worker pid=759) ERROR 10-17 11:41:28 [multiproc_executor.py:857]     worker = WorkerProc(*args, **kwargs)\n"}
,{"stream_name":"stderr","time":391.867660744,"data":"(Worker pid=759) ERROR 10-17 11:41:28 [multiproc_executor.py:857]              ^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":391.867662639,"data":"(Worker pid=759) ERROR 10-17 11:41:28 [multiproc_executor.py:857]   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/executor/multiproc_executor.py\", line 605, in __init__\n"}
,{"stream_name":"stderr","time":391.867666795,"data":"(Worker pid=759) ERROR 10-17 11:41:28 [multiproc_executor.py:857]     self.worker.init_device()\n"}
,{"stream_name":"stderr","time":391.867668756,"data":"(Worker pid=759) ERROR 10-17 11:41:28 [multiproc_executor.py:857]   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/worker/worker_base.py\", line 312, in init_device\n"}
,{"stream_name":"stderr","time":391.867670823,"data":"(Worker pid=759) ERROR 10-17 11:41:28 [multiproc_executor.py:857]     self.worker.init_device()  # type: ignore\n"}
,{"stream_name":"stderr","time":391.86767269,"data":"(Worker pid=759) ERROR 10-17 11:41:28 [multiproc_executor.py:857]     ^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":391.86767464,"data":"(Worker pid=759) ERROR 10-17 11:41:28 [multiproc_executor.py:857]   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/worker/gpu_worker.py\", line 283, in init_device\n"}
,{"stream_name":"stderr","time":391.867676889,"data":"(Worker pid=759) ERROR 10-17 11:41:28 [multiproc_executor.py:857]     self.requested_memory = request_memory(init_snapshot, self.cache_config)\n"}
,{"stream_name":"stderr","time":391.867678875,"data":"(Worker pid=759) ERROR 10-17 11:41:28 [multiproc_executor.py:857]                             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":391.867682707,"data":"(Worker pid=759) ERROR 10-17 11:41:28 [multiproc_executor.py:857]   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/worker/utils.py\", line 413, in request_memory\n"}
,{"stream_name":"stderr","time":391.867685076,"data":"(Worker pid=759) ERROR 10-17 11:41:28 [multiproc_executor.py:857]     raise ValueError(\n"}
,{"stream_name":"stderr","time":391.867686959,"data":"(Worker pid=759) ERROR 10-17 11:41:28 [multiproc_executor.py:857] ValueError: Free memory on device cuda:1 (16.64/22.03 GiB) on startup is less than desired GPU memory utilization (0.85, 18.73 GiB). Decrease GPU memory utilization or reduce GPU memory used by other processes.\n"}
,{"stream_name":"stderr","time":391.867689344,"data":"[rank0]:[W1017 11:41:29.445333484 ProcessGroupNCCL.cpp:1553] Warning: WARNING: destroy_process_group() was not called before program exit, which can leak resources. For more info, please see https://pytorch.org/docs/stable/distributed.html#shutdown (function operator())\n"}
,{"stream_name":"stderr","time":391.867691558,"data":"(EngineCore pid=597) ERROR 10-17 11:41:30 [core.py:1108] EngineCore failed to start.\n"}
,{"stream_name":"stderr","time":391.8676934,"data":"(EngineCore pid=597) ERROR 10-17 11:41:30 [core.py:1108] Traceback (most recent call last):\n"}
,{"stream_name":"stderr","time":391.867695355,"data":"(EngineCore pid=597) ERROR 10-17 11:41:30 [core.py:1108]   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/engine/core.py\", line 1082, in run_engine_core\n"}
,{"stream_name":"stderr","time":391.867697486,"data":"(EngineCore pid=597) ERROR 10-17 11:41:30 [core.py:1108]     engine_core = EngineCoreProc(*args, engine_index=dp_rank, **kwargs)\n"}
,{"stream_name":"stderr","time":391.867699486,"data":"(EngineCore pid=597) ERROR 10-17 11:41:30 [core.py:1108]                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":391.86770145,"data":"(EngineCore pid=597) ERROR 10-17 11:41:30 [core.py:1108]   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/engine/core.py\", line 848, in __init__\n"}
,{"stream_name":"stderr","time":391.867703512,"data":"(EngineCore pid=597) ERROR 10-17 11:41:30 [core.py:1108]     super().__init__(\n"}
,{"stream_name":"stderr","time":391.86770534,"data":"(EngineCore pid=597) ERROR 10-17 11:41:30 [core.py:1108]   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/engine/core.py\", line 114, in __init__\n"}
,{"stream_name":"stderr","time":391.867707337,"data":"(EngineCore pid=597) ERROR 10-17 11:41:30 [core.py:1108]     self.model_executor = executor_class(vllm_config)\n"}
,{"stream_name":"stderr","time":391.867709234,"data":"(EngineCore pid=597) ERROR 10-17 11:41:30 [core.py:1108]                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":391.867711223,"data":"(EngineCore pid=597) ERROR 10-17 11:41:30 [core.py:1108]   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/executor/multiproc_executor.py\", line 101, in __init__\n"}
,{"stream_name":"stderr","time":391.867713292,"data":"(EngineCore pid=597) ERROR 10-17 11:41:30 [core.py:1108]     super().__init__(vllm_config)\n"}
,{"stream_name":"stderr","time":391.867715207,"data":"(EngineCore pid=597) ERROR 10-17 11:41:30 [core.py:1108]   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/executor/abstract.py\", line 103, in __init__\n"}
,{"stream_name":"stderr","time":391.867717444,"data":"(EngineCore pid=597) ERROR 10-17 11:41:30 [core.py:1108]     self._init_executor()\n"}
,{"stream_name":"stderr","time":391.867719275,"data":"(EngineCore pid=597) ERROR 10-17 11:41:30 [core.py:1108]   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/executor/multiproc_executor.py\", line 190, in _init_executor\n"}
,{"stream_name":"stderr","time":391.867721667,"data":"(EngineCore pid=597) ERROR 10-17 11:41:30 [core.py:1108]     self.workers = WorkerProc.wait_for_ready(unready_workers)\n"}
,{"stream_name":"stderr","time":391.867725244,"data":"(EngineCore pid=597) ERROR 10-17 11:41:30 [core.py:1108]                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":391.867727439,"data":"(EngineCore pid=597) ERROR 10-17 11:41:30 [core.py:1108]   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/executor/multiproc_executor.py\", line 736, in wait_for_ready\n"}
,{"stream_name":"stderr","time":391.86772966,"data":"(EngineCore pid=597) ERROR 10-17 11:41:30 [core.py:1108]     raise e from None\n"}
,{"stream_name":"stderr","time":391.867731527,"data":"(EngineCore pid=597) ERROR 10-17 11:41:30 [core.py:1108] Exception: WorkerProc initialization failed due to an exception in a background process. See stack trace for root cause.\n"}
,{"stream_name":"stderr","time":391.867733621,"data":"(EngineCore pid=597) Process EngineCore:\n"}
,{"stream_name":"stderr","time":391.867735436,"data":"(EngineCore pid=597) Traceback (most recent call last):\n"}
,{"stream_name":"stderr","time":391.867737245,"data":"(EngineCore pid=597)   File \"/usr/lib/python3.12/multiprocessing/process.py\", line 314, in _bootstrap\n"}
,{"stream_name":"stderr","time":391.867739232,"data":"(EngineCore pid=597)     self.run()\n"}
,{"stream_name":"stderr","time":391.867740991,"data":"(EngineCore pid=597)   File \"/usr/lib/python3.12/multiprocessing/process.py\", line 108, in run\n"}
,{"stream_name":"stderr","time":391.867742943,"data":"(EngineCore pid=597)     self._target(*self._args, **self._kwargs)\n"}
,{"stream_name":"stderr","time":391.867744904,"data":"(EngineCore pid=597)   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/engine/core.py\", line 1112, in run_engine_core\n"}
,{"stream_name":"stderr","time":391.86774696,"data":"(EngineCore pid=597)     raise e\n"}
,{"stream_name":"stderr","time":391.867748787,"data":"(EngineCore pid=597)   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/engine/core.py\", line 1082, in run_engine_core\n"}
,{"stream_name":"stderr","time":391.867750815,"data":"(EngineCore pid=597)     engine_core = EngineCoreProc(*args, engine_index=dp_rank, **kwargs)\n"}
,{"stream_name":"stderr","time":391.867752684,"data":"(EngineCore pid=597)                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":391.867754527,"data":"(EngineCore pid=597)   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/engine/core.py\", line 848, in __init__\n"}
,{"stream_name":"stderr","time":391.867756487,"data":"(EngineCore pid=597)     super().__init__(\n"}
,{"stream_name":"stderr","time":391.867758247,"data":"(EngineCore pid=597)   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/engine/core.py\", line 114, in __init__\n"}
,{"stream_name":"stderr","time":391.867760288,"data":"(EngineCore pid=597)     self.model_executor = executor_class(vllm_config)\n"}
,{"stream_name":"stderr","time":391.867762187,"data":"(EngineCore pid=597)                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":391.867764316,"data":"(EngineCore pid=597)   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/executor/multiproc_executor.py\", line 101, in __init__\n"}
,{"stream_name":"stderr","time":391.867766357,"data":"(EngineCore pid=597)     super().__init__(vllm_config)\n"}
,{"stream_name":"stderr","time":391.867768137,"data":"(EngineCore pid=597)   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/executor/abstract.py\", line 103, in __init__\n"}
,{"stream_name":"stderr","time":391.8677701,"data":"(EngineCore pid=597)     self._init_executor()\n"}
,{"stream_name":"stderr","time":391.867771872,"data":"(EngineCore pid=597)   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/executor/multiproc_executor.py\", line 190, in _init_executor\n"}
,{"stream_name":"stderr","time":391.867775894,"data":"(EngineCore pid=597)     self.workers = WorkerProc.wait_for_ready(unready_workers)\n"}
,{"stream_name":"stderr","time":391.867778024,"data":"(EngineCore pid=597)                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":391.867779943,"data":"(EngineCore pid=597)   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/executor/multiproc_executor.py\", line 736, in wait_for_ready\n"}
,{"stream_name":"stderr","time":391.86778198,"data":"(EngineCore pid=597)     raise e from None\n"}
,{"stream_name":"stderr","time":391.867783796,"data":"(EngineCore pid=597) Exception: WorkerProc initialization failed due to an exception in a background process. See stack trace for root cause.\n"}
,{"stream_name":"stderr","time":391.867785809,"data":"(APIServer pid=276) Traceback (most recent call last):\n"}
,{"stream_name":"stderr","time":391.86778759,"data":"(APIServer pid=276)   File \"\u003cfrozen runpy\u003e\", line 198, in _run_module_as_main\n"}
,{"stream_name":"stderr","time":391.867789615,"data":"(APIServer pid=276)   File \"\u003cfrozen runpy\u003e\", line 88, in _run_code\n"}
,{"stream_name":"stderr","time":391.867791579,"data":"(APIServer pid=276)   File \"/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/openai/api_server.py\", line 712, in \u003cmodule\u003e\n"}
,{"stream_name":"stderr","time":391.867793884,"data":"(APIServer pid=276)     uvloop.run(run_server(args))\n"}
,{"stream_name":"stderr","time":391.867795747,"data":"(APIServer pid=276)   File \"/usr/local/lib/python3.12/dist-packages/uvloop/__init__.py\", line 96, in run\n"}
,{"stream_name":"stderr","time":391.867797754,"data":"(APIServer pid=276)     return __asyncio.run(\n"}
,{"stream_name":"stderr","time":391.867799542,"data":"(APIServer pid=276)            ^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":391.867801344,"data":"(APIServer pid=276)   File \"/usr/lib/python3.12/asyncio/runners.py\", line 195, in run\n"}
,{"stream_name":"stderr","time":391.867803324,"data":"(APIServer pid=276)     return runner.run(main)\n"}
,{"stream_name":"stderr","time":391.867805172,"data":"(APIServer pid=276)            ^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":391.867807046,"data":"(APIServer pid=276)   File \"/usr/lib/python3.12/asyncio/runners.py\", line 118, in run\n"}
,{"stream_name":"stderr","time":391.867809308,"data":"(APIServer pid=276)     return self._loop.run_until_complete(task)\n"}
,{"stream_name":"stderr","time":391.867811173,"data":"(APIServer pid=276)            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":391.867813128,"data":"(APIServer pid=276)   File \"uvloop/loop.pyx\", line 1518, in uvloop.loop.Loop.run_until_complete\n"}
,{"stream_name":"stderr","time":391.867815344,"data":"(APIServer pid=276)   File \"/usr/local/lib/python3.12/dist-packages/uvloop/__init__.py\", line 48, in wrapper\n"}
,{"stream_name":"stderr","time":391.867817327,"data":"(APIServer pid=276)     return await main\n"}
,{"stream_name":"stderr","time":391.867819165,"data":"(APIServer pid=276)            ^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":391.867820925,"data":"(APIServer pid=276)   File \"/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/openai/api_server.py\", line 672, in run_server\n"}
,{"stream_name":"stderr","time":391.867822924,"data":"(APIServer pid=276)     await run_server_worker(listen_address, sock, args, **uvicorn_kwargs)\n"}
,{"stream_name":"stderr","time":391.867825007,"data":"(APIServer pid=276)   File \"/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/openai/api_server.py\", line 686, in run_server_worker\n"}
,{"stream_name":"stderr","time":391.86782937,"data":"(APIServer pid=276)     async with build_async_engine_client(\n"}
,{"stream_name":"stderr","time":391.867831393,"data":"(APIServer pid=276)                ^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":391.86783325,"data":"(APIServer pid=276)   File \"/usr/lib/python3.12/contextlib.py\", line 210, in __aenter__\n"}
,{"stream_name":"stderr","time":391.86783518,"data":"(APIServer pid=276)     return await anext(self.gen)\n"}
,{"stream_name":"stderr","time":391.86783697,"data":"(APIServer pid=276)            ^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":391.867838771,"data":"(APIServer pid=276)   File \"/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/openai/api_server.py\", line 100, in build_async_engine_client\n"}
,{"stream_name":"stderr","time":391.867840755,"data":"(APIServer pid=276)     async with build_async_engine_client_from_engine_args(\n"}
,{"stream_name":"stderr","time":391.867842759,"data":"(APIServer pid=276)                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":391.867844647,"data":"(APIServer pid=276)   File \"/usr/lib/python3.12/contextlib.py\", line 210, in __aenter__\n"}
,{"stream_name":"stderr","time":391.867846627,"data":"(APIServer pid=276)     return await anext(self.gen)\n"}
,{"stream_name":"stderr","time":391.867848464,"data":"(APIServer pid=276)            ^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":391.867850255,"data":"(APIServer pid=276)   File \"/usr/local/lib/python3.12/dist-packages/vllm/entrypoints/openai/api_server.py\", line 136, in build_async_engine_client_from_engine_args\n"}
,{"stream_name":"stderr","time":391.867852267,"data":"(APIServer pid=276)     async_llm = AsyncLLM.from_vllm_config(\n"}
,{"stream_name":"stderr","time":391.867854092,"data":"(APIServer pid=276)                 ^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":391.867855907,"data":"(APIServer pid=276)   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/engine/async_llm.py\", line 225, in from_vllm_config\n"}
,{"stream_name":"stderr","time":391.867858021,"data":"(APIServer pid=276)     return cls(\n"}
,{"stream_name":"stderr","time":391.867859839,"data":"(APIServer pid=276)            ^^^^\n"}
,{"stream_name":"stderr","time":391.867861657,"data":"(APIServer pid=276)   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/engine/async_llm.py\", line 154, in __init__\n"}
,{"stream_name":"stderr","time":391.867863629,"data":"(APIServer pid=276)     self.engine_core = EngineCoreClient.make_async_mp_client(\n"}
,{"stream_name":"stderr","time":391.867865794,"data":"(APIServer pid=276)                        ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":391.867867642,"data":"(APIServer pid=276)   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/engine/core_client.py\", line 130, in make_async_mp_client\n"}
,{"stream_name":"stderr","time":391.867869662,"data":"(APIServer pid=276)     return AsyncMPClient(*client_args)\n"}
,{"stream_name":"stderr","time":391.867871575,"data":"(APIServer pid=276)            ^^^^^^^^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":391.867873479,"data":"(APIServer pid=276)   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/engine/core_client.py\", line 887, in __init__\n"}
,{"stream_name":"stderr","time":391.867875527,"data":"(APIServer pid=276)     super().__init__(\n"}
,{"stream_name":"stderr","time":391.867877324,"data":"(APIServer pid=276)   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/engine/core_client.py\", line 535, in __init__\n"}
,{"stream_name":"stderr","time":391.867879274,"data":"(APIServer pid=276)     with launch_core_engines(\n"}
,{"stream_name":"stderr","time":391.867882905,"data":"(APIServer pid=276)          ^^^^^^^^^^^^^^^^^^^^\n"}
,{"stream_name":"stderr","time":391.867884871,"data":"(APIServer pid=276)   File \"/usr/lib/python3.12/contextlib.py\", line 144, in __exit__\n"}
,{"stream_name":"stderr","time":391.867886764,"data":"(APIServer pid=276)     next(self.gen)\n"}
,{"stream_name":"stderr","time":391.867888509,"data":"(APIServer pid=276)   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/engine/utils.py\", line 998, in launch_core_engines\n"}
,{"stream_name":"stderr","time":391.867890669,"data":"(APIServer pid=276)     wait_for_engine_startup(\n"}
,{"stream_name":"stderr","time":391.867892529,"data":"(APIServer pid=276)   File \"/usr/local/lib/python3.12/dist-packages/vllm/v1/engine/utils.py\", line 1057, in wait_for_engine_startup\n"}
,{"stream_name":"stderr","time":391.86789457,"data":"(APIServer pid=276)     raise RuntimeError(\n"}
,{"stream_name":"stderr","time":391.867896381,"data":"(APIServer pid=276) RuntimeError: Engine core initialization failed. See root cause above. Failed core proc(s): {}\n"}
,{"stream_name":"stderr","time":391.86789831,"data":"/usr/lib/python3.12/multiprocessing/resource_tracker.py:279: UserWarning: resource_tracker: There appear to be 1 leaked shared_memory objects to clean up at shutdown\n"}
,{"stream_name":"stderr","time":391.867900319,"data":"  warnings.warn('resource_tracker: There appear to be %d '\n"}
,{"stream_name":"stderr","time":391.867902131,"data":"\n"}
,{"stream_name":"stderr","time":391.867903812,"data":"\n"}
,{"stream_name":"stderr","time":394.131840971,"data":"/usr/local/lib/python3.12/dist-packages/mistune.py:435: SyntaxWarning: invalid escape sequence '\\|'\n"}
,{"stream_name":"stderr","time":394.131864422,"data":"  cells[i][c] = re.sub('\\\\\\\\\\|', '|', cell)\n"}
,{"stream_name":"stderr","time":394.278854826,"data":"/usr/local/lib/python3.12/dist-packages/nbconvert/filters/filter_links.py:36: SyntaxWarning: invalid escape sequence '\\_'\n"}
,{"stream_name":"stderr","time":394.278876574,"data":"  text = re.sub(r'_', '\\_', text) # Escape underscores in display text\n"}
,{"stream_name":"stderr","time":395.003806321,"data":"[NbConvertApp] Converting notebook __notebook__.ipynb to notebook\n"}
,{"stream_name":"stderr","time":395.326602337,"data":"[NbConvertApp] Writing 98960 bytes to __notebook__.ipynb\n"}
,{"stream_name":"stderr","time":397.970535713,"data":"[NbConvertApp] Converting notebook __notebook__.ipynb to html\n"}
,{"stream_name":"stderr","time":398.81775932,"data":"[NbConvertApp] Writing 383324 bytes to __results__.html\n"}
]
