from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ChannelStyle:
    name: str
    description: str
    language: str = "pt-BR"


DEFAULT_CHANNEL_STYLE = ChannelStyle(
    name="Arquivo Oculto",
    description=(
        "Arquivo Oculto investiga mistérios reais, casos não resolvidos, desaparecimentos documentados, "
        "eventos históricos controversos e evidências que desafiam explicações oficiais. "
        "Aqui você encontra relatos investigativos, histórias reais e análises de casos intrigantes que continuam gerando perguntas. "
        "Toda semana publicamos vídeos curtos investigativos com narrativa cinematográfica e base documental."
    ),
    language="pt-BR",
)


def build_investigative_short_prompt(
    wiki_extract: str,
    extra_context: str = "",
    target_seconds: int = 60,
    max_words: int = 155,
    channel_style: ChannelStyle = DEFAULT_CHANNEL_STYLE,
    include_source_line: bool = True,
) -> str:
    """Prompt para gerar roteiro curto investigativo, seguro para YouTube.

    Importante:
    - Deve ser factual e baseado no trecho documental fornecido.
    - Deve evitar detalhes explícitos (gore), sexo/menores, ódio, instruções de armas, etc.
    """
    source_line = (
        "\n\nInclua UMA linha discreta no final com: 'Fonte: Wikipédia (consulta local)'."
        if include_source_line
        else ""
    )

    return f"""
Você é um roteirista de vídeos curtos (YouTube Shorts) no estilo do canal \"{channel_style.name}\".

Descrição do canal (tom e intenção):
{channel_style.description}

Tarefa:
- Escreva um roteiro narrado em PT-BR com ritmo cinematográfico e investigativo.
- Duração alvo: ~{target_seconds}s.
- Limite: no máximo {max_words} palavras (se possível, 135–{max_words}).

Estrutura obrigatória (bem compacta):
1) Gancho (1–2 frases, forte, sem clickbait barato)
2) Linha do tempo / fatos-chave (3–6 frases curtas)
3) Contradição / detalhe intrigante (1–2 frases)
4) Fecho com pergunta (1 frase)

Regras de segurança (YouTube-friendly):
- NÃO descreva violência gráfica, gore, corpos ou ferimentos em detalhe.
- NÃO inclua conteúdo sexual, especialmente envolvendo menores (nunca).
- NÃO use discurso de ódio, slurs ou propaganda extremista.
- NÃO dê instruções de armas, explosivos ou crimes.
- Se houver suicídio/autoagressão no tema, trate com linguagem suave e sem detalhes.

Base documental (use apenas o que está aqui; não invente fatos específicos como nomes, datas ou locais se não estiverem no texto):

<CONTEXTO_EXTRA>
{(extra_context or '').strip()}
</CONTEXTO_EXTRA>

<DOCUMENTO>
{(wiki_extract or "").strip()}
</DOCUMENTO>

Instruções finais:
- Escreva em parágrafos curtos (1–2 frases por parágrafo).
- Sem listas, sem emojis.
- Evite termos explícitos (substitua por linguagem suave quando necessário).
{source_line}
""".strip()
