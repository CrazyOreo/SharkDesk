# 🦈 SharkDesk

Sistema de Acesso Remoto e Suporte Técnico desenvolvido como projeto acadêmico do curso de Ciência da Computação da Universidade Católica de Santos (UniSantos).

O SharkDesk é uma solução de acesso remoto inspirada em softwares amplamente utilizados no mercado, como AnyDesk e TeamViewer, permitindo comunicação entre um especialista e um cliente através de uma conexão TCP para compartilhamento de tela, troca de mensagens e suporte remoto.

---

## 📋 Sobre o Projeto

O projeto foi desenvolvido com o objetivo de aplicar conceitos estudados durante a graduação, envolvendo áreas como:

- Redes de Computadores
- Sistemas Distribuídos
- Programação Concorrente
- Engenharia de Software
- Desenvolvimento de Interfaces Gráficas
- Comunicação Cliente-Servidor

O sistema permite que um computador atue como servidor (Especialista) e outro como cliente (Usuário), estabelecendo uma conexão para assistência remota.

---

## ✨ Funcionalidades

### 👨‍💻 Especialista (Servidor)

- Criação automática de sessão
- Recebimento de conexões remotas
- Visualização da tela do cliente
- Chat integrado
- Monitoramento da conexão
- Gerenciamento da sessão

### 🖥️ Cliente (Usuário)

- Conexão por código de acesso
- Compartilhamento de tela em tempo real
- Comunicação por chat
- Controle da sessão
- Interface simplificada

---

## 🏗️ Arquitetura

```text
┌──────────────────┐
│   Especialista   │
│    (Servidor)    │
└────────┬─────────┘
         │
         │ TCP Socket
         │
┌────────▼─────────┐
│    SharkDesk     │
│ Camada de Rede   │
└────────┬─────────┘
         │
         │
┌────────▼─────────┐
│     Cliente      │
│    (Usuário)     │
└──────────────────┘
```

A comunicação é baseada em sockets TCP e utiliza múltiplas threads para permitir transmissão simultânea de mensagens, eventos e compartilhamento de tela.

---

## 🛠️ Tecnologias Utilizadas

- Python 3
- Flet
- Socket TCP
- Threading
- OpenCV
- MSS
- Pillow
- PyAutoGUI
- PyInstaller

---

## 📂 Estrutura do Projeto

```text
SharkDesk/
│
├── sharkdesk_server.py
├── sharkdesk_client.py
├── README.md
│
└── dist/
    └── SharkDesk.exe
```

### Arquivos Principais

| Arquivo             | Descrição                                |
| ------------------- | ---------------------------------------- |
| sharkdesk_server.py | Implementação do servidor (Especialista) |
| sharkdesk_client.py | Implementação do cliente (Usuário)       |
| SharkDesk.exe       | Versão compilada para Windows            |

---

## 🚀 Execução do Projeto

### Utilizando o Executável

O projeto já possui uma versão compilada para Windows.

1. Acesse a pasta:

```text
dist/
```

2. Execute:

```text
SharkDesk.exe
```

3. Escolha o modo desejado:

- Especialista (Servidor)
- Cliente (Usuário)

Nenhuma instalação adicional é necessária.

---

### Executando pelo Código-Fonte

Instale as dependências:

```bash
pip install -r requirements.txt
```

Execute o servidor:

```bash
python sharkdesk_server.py
```

Execute o cliente:

```bash
python sharkdesk_client.py
```

---

## 🔐 Aspectos de Segurança

O sistema implementa mecanismos básicos de segurança para fins acadêmicos:

- Validação de conexão
- Código de acesso para identificação da sessão
- Encerramento seguro de conexões
- Isolamento das sessões ativas

---

## 📚 Conceitos Aplicados

Durante o desenvolvimento foram utilizados conceitos relacionados a:

- Comunicação Cliente-Servidor
- Programação Concorrente
- Multithreading
- Sockets TCP
- Compartilhamento de Tela
- Processamento de Imagens
- Interfaces Gráficas
- Sistemas Distribuídos
- Engenharia de Software

---

## 👥 Equipe de Desenvolvimento

### Made with GAM

#### Pedro Henrique Novais

- Arquitetura de Sockets
- Design do Protocolo Binário
- Tratamento de frames de vídeo e texto

#### Jefferson Alves Andrade Salgado

- Gerenciamento de Threads
- Desenvolvimento da Interface com Flet
- Testes de concorrência
- Análise de condições de corrida

#### Tiago Xavier

- Documentação Teórica (ABNT)
- Validação de requisitos funcionais
- Elaboração de fluxogramas arquiteturais

#### Luiz Anselmo

- Documentação Teórica (ABNT)
- Validação de requisitos funcionais
- Elaboração de fluxogramas arquiteturais

---

## 📊 Divisão de Responsabilidades

| Integrante                      | Responsabilidades                                                |
| ------------------------------- | ---------------------------------------------------------------- |
| Pedro Henrique Novais           | Arquitetura de Sockets, protocolo binário e transmissão de dados |
| Jefferson Alves Andrade Salgado | Threads, interface gráfica em Flet e sincronização               |
| Tiago Xavier                    | Documentação ABNT, modelagem e requisitos funcionais             |
| Luiz Anselmo                    | Documentação ABNT, modelagem e requisitos funcionais             |

---

## 🏫 Instituição

Universidade Católica de Santos (UniSantos)

Curso: Ciência da Computação

Projeto desenvolvido para fins acadêmicos como aplicação prática dos conceitos estudados durante a graduação.

---

## 👨‍🎓 Autores

- Jefferson Alves Andrade Salgado
- Pedro Henrique Novais
- Tiago Xavier
- Luiz Anselmo

---

## ⚠️ Aviso

Este projeto possui finalidade exclusivamente acadêmica e educacional.

O SharkDesk foi desenvolvido como estudo de tecnologias de acesso remoto e não possui qualquer afiliação com AnyDesk®, TeamViewer® ou outras soluções comerciais.

Todas as marcas mencionadas pertencem aos seus respectivos proprietários.
