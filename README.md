![Preview](image.png)

Stages:
- Lexer: dsl_lexer.py
- Parser: dsl_parser.py
- AST: dsl_ast.py
- Type checker: dsl_typecheck.py
- AST interpreter: dsl_interp_ast.py
- IR: dsl_ir.py
- IR interpreter: dsl_interp_ir.py
- GLSL emitter (AST): dsl_glsl.py
- GLSL emitter (IR): dsl_glsl_ir.py
- Tests: main.py
- LLM frontend: openrouter_client.py, dsl_prompt.py

Quick start
1) Run tests
	/Users/saiganesh/dev/geometry-dsl/.venv/bin/python main.py

2) Setup environment (for LLM generation)
	cp .env.example .env
	Edit .env with your OpenRouter API key (get one at https://openrouter.ai)

3) Install dependencies  
	pip install fastapi uvicorn httpx

4) Start backend
	/Users/saiganesh/dev/geometry-dsl/.venv/bin/uvicorn server:app --reload

5) Open frontend
	Open index.html in a browser

Workflow
- Click "Render" to compile and display DSL in the viewport
- Type an English description in the text field and click "Generate" to create DSL via LLM
- The generated code is inserted into the DSL editor and auto-compiled

Optional manual check
curl -s -X POST http://localhost:8000/eval \
	-H 'Content-Type: application/json' \
	-d '{"code":"sphere(1)","p":[0,0,0]}'
