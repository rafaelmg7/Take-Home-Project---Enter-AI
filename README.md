# Take-Home-Project---Enter-AI

Repositório contendo a implementação de um extrator de dados estruturados de PDFs para o desafio técnico do programa de fellowship da Enter AI

## Contexto e Abordagem

Inicialmente, reconheci que não sou um especialista em extração de dados estruturados e uso de LLMs para tais tarefas; portanto, comecei uma ampla revisão da literatura e compreensão de conceitos necessários para a realização da tarefa. Isso me levou a leituras interessantes e até a artigos que, para minha surpresa, cobriam esse tipo de tarefa (por exemplo, este estudo clínico: https://bmcmedinformdecismak.biomedcentral.com/articles/10.1186/s12911-024-02698-7?utm_source=chatgpt.com#Sec5).

Na primeira tentativa, modelei o problema supondo que a melhor estratégia seria gerar previamente artefatos de extração por label (listas de palavras-âncora, dicas de localização e regras de normalização/validação) via LLM e cacheá-los. A ideia era transformar conhecimento semântico em regras determinísticas reutilizáveis. Em execução, heurísticas tentariam localizar rapidamente valores (chaves, padrões, fuzzy) e apenas em casos incertos a LLM seria chamada. Porém, o custo de prompt, a latência e a baixa precisão inicial das heurísticas levaram a mais chamadas de LLM que o planejado e adicionaram complexidade desnecessária.

Frente esses problemas, busquei entender a razão pela qual minha ideia não funcionou e o que eu poderia fazer de diferente. Parti, então, do pressuposto de que o melhor jeito de usar a LLM seria enviando partes do arquivo a ela como contexto junto ao extraction_schema, de modo que ela - que notavelmente captura melhor conceitos do que heurísticas - relacione as informações de cada campo com o conteúdo do PDF. Assim, pensei em jeitos intuitivos de buscar valores nos textos e validei minhas ideias com uma revisão de heurísticas já consolidadas. Cheguei à seguinte abordagem: em vez de pré-gerar muitos artefatos, uso heurísticas enxutas sobre o texto completo e só aciono a LLM como fallback para campos que permanecem incertos dentro da janela de tempo. As heurísticas atuais concentram-se em:

- Âncoras normalizadas derivadas do nome do campo (variações simples).
- Extração na mesma linha (padrões "Anchor: Valor" ou "Anchor - Valor").
- Extração na linha seguinte quando a linha atual parece apenas um rótulo.
- Deduplicação e normalização leve (remover acentos, caixa, espaços).
- Escoragem simples: peso maior para match de âncora, seguido de posição aproximada (top/bottom) e presença em enumeração conhecida.
- Limiares: >=0.8 aceita; <0.6 marca como incerto; entre eles pode ser aceito via LLM.
- Aprendizado incremental mínimo: adiciona novas âncoras observadas e estima regiões dominantes para cada campo a partir de extrações confirmadas.

Decisões principais de projeto: privilegiar simplicidade e auditabilidade; evitar regex e heurísticas prolixas até que haja evidência de ganho; manter tempo de resposta curto com limites estritos; separar claramente normalização de valores (preservar forma original) da normalização para comparação; usar estrutura de candidato com pesos fixos para facilitar ajuste futuro; atualizar a KB de forma oportunista sem reprocessamentos caros. Esta abordagem reduz custo cognitivo e operacional, mantém o código legível e prepara terreno para evoluções incrementais controladas.

## Funcionalidades

- **Parsing rápido de PDF** com PyMuPDF (fitz)
- **API RESTful** construída com FastAPI
- **Extração estruturada** com metadados posicionais em nível de linha
- **Proteção por timeout** (9s padrão)
- **Type-safe** com type hints do Python
- **Suporte assíncrono** para requisições concorrentes

## Requisitos

- Python 3.10+
- Dependências listadas em `requirements.txt`

## Tutorial Rápido (Resumo)

```bash
# Instalar dependências
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Iniciar servidor
python run_server.py --reload

# Fazer requisição de extração
curl -X POST http://127.0.0.1:8000/extract \
  -F 'label=oab_card' \
  -F 'schema={"nome":"Name","inscricao":"Registration"}' \
  -F 'pdf=@examples/oab_1.pdf'
```

Resposta conterá campos, metadados e evidências heurísticas/LLM.
