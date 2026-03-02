# Validação Automática do Catálogo de Presets

Este patch adiciona:

1) Validador estrutural do JSON do catálogo
2) Checagem de IDs duplicados
3) Checagem de pesos inválidos
4) Criação automática de catálogo default caso não exista

## PowerShell

Validar:
  .\tools\validate_catalog.ps1

Criar default se estiver ausente:
  .\tools\validate_catalog.ps1 -FixIfMissing

## Comportamento Esperado

Se o catálogo estiver inválido, erros serão exibidos.
Se estiver ausente e auto_create_default_if_missing = true,
um catálogo mínimo será criado automaticamente.
