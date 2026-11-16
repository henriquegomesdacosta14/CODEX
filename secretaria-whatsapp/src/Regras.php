<?php

namespace Secretaria;

/**
 * Regras que a equipe ensina à secretária pelo simulador ("Sempre pergunte
 * se é a primeira consulta"). Ficam em dados/regras_aprendidas.json e são
 * incluídas nas instruções das próximas conversas.
 */
class Regras
{
    private const MAX_REGRAS = 40;
    private const MAX_TEXTO = 600;

    public function __construct(private Armazenamento $armazenamento)
    {
    }

    public function listar(): array
    {
        return $this->armazenamento->ler('regras_aprendidas', []);
    }

    /** @return array{ok:bool, erro?:string, regra?:array} */
    public function adicionar(string $texto, string $autor = ''): array
    {
        $texto = trim(preg_replace('/\s+/u', ' ', $texto));
        if (mb_strlen($texto) < 5) {
            return ['ok' => false, 'erro' => 'Escreva a regra com um pouco mais de detalhe.'];
        }
        if (mb_strlen($texto) > self::MAX_TEXTO) {
            return ['ok' => false, 'erro' => 'A regra está muito longa (máximo ' . self::MAX_TEXTO . ' letras). Divida em duas.'];
        }
        $regra = ['id' => 'r' . bin2hex(random_bytes(4)), 'texto' => $texto, 'autor' => mb_substr($autor, 0, 40), 'em' => date('c')];

        $erro = $this->armazenamento->atualizar('regras_aprendidas', function (array $lista) use ($regra) {
            foreach ($lista as $r) {
                if (mb_strtolower($r['texto']) === mb_strtolower($regra['texto'])) {
                    return [$lista, 'Essa regra já existe.'];
                }
            }
            if (count($lista) >= self::MAX_REGRAS) {
                return [$lista, 'Já são ' . self::MAX_REGRAS . ' regras. Apague alguma antes de adicionar outra.'];
            }
            $lista[] = $regra;
            return [$lista, null];
        }, []);

        return $erro ? ['ok' => false, 'erro' => $erro] : ['ok' => true, 'regra' => $regra];
    }

    public function excluir(string $id): void
    {
        $this->armazenamento->atualizar('regras_aprendidas', fn (array $lista) => [
            array_values(array_filter($lista, fn ($r) => $r['id'] !== $id)), null,
        ], []);
    }

    /** Texto para as instruções da IA ('' se não houver regras). */
    public function paraInstrucoes(): string
    {
        $lista = $this->listar();
        if (!$lista) {
            return '';
        }
        return "\n\n## Regras ensinadas pela equipe da clínica (sempre siga; têm prioridade sobre o estilo padrão)\n"
            . implode("\n", array_map(fn ($r) => '- ' . $r['texto'], $lista)) . "\n";
    }
}
