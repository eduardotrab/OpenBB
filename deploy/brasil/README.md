# OpenBB Brasil — implantação

Instala o OpenBB deste fork com os providers brasileiros (`bcb`, `ibge`, `tesouro`, `cvm`, `receita`) e os sobe como serviços systemd de usuário.

| Arquivo | Função |
|---|---|
| `deploy.sh` | Instalação/atualização do zero: clona o fork, cria o venv, instala, cria `openbb.toml`, teste de fumaça, serviços. |
| `install_openbb.py` | Roda `openbb_platform/dev_install.py` excluindo `providers/eia` (não constrói sem chave da EIA). |
| `install_services.sh` | Gera e habilita `openbb-api.service` (6900) e `openbb-mcp.service` (6901). |
| `openbb.toml` | Modelo da configuração: portas (fora de 8000–8050 e 9000–9050) e feeds de notícias `gov_br`. |
| `systemd/*.service` | Modelos das units (`@PROJECT_DIR@` é substituído). |

## Uso (Linux Mint / Ubuntu / Debian)

```sh
sudo apt install git python3-venv pipx      # se faltar algo
bash deploy.sh ~/openbb-brasil               # ~15 min na primeira vez
```

Verificar: `curl http://127.0.0.1:6900/docs` e `systemctl --user status openbb-api openbb-mcp`.
Logs: `journalctl --user -u openbb-api -f`. Atualizar: rodar `deploy.sh` de novo (mantém o `openbb.toml`).

Para os serviços rodarem sem sessão aberta: `sudo loginctl enable-linger $USER`.
