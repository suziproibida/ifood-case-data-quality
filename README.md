# Projeto Lakehouse — Data Quality NYC Taxi

> Uma jornada de dados: da fonte bruta ao consumo analítico confiável.

---

## A Visão: Arquitetura e Estrutura

### O Problema

Dados de táxi da cidade de Nova York chegam em formatos diferentes, com inconsistências de nomenclatura, registros inválidos e sem qualquer rastreabilidade. O objetivo foi construir uma arquitetura moderna de **Data Lakehouse** capaz de transformar esse caos em dados confiáveis e prontos para análise.

### A Solução: Arquitetura em Camadas

A solução foi desenhada como um pipeline sequencial, onde cada camada tem uma responsabilidade clara:

```text
RAW          → Dados exatamente como chegam da fonte
↓
LANDING      → Rastreabilidade e identificação dos registros
↓
VALIDAÇÕES
├── TRUSTED  → Registros válidos, prontos para consumo
└── REJECTED → Registros inválidos, catalogados com o motivo
↓
CONSUMPTION  → Visão unificada e analítica
```

### Tecnologias Escolhidas

| Camada        | Tecnologia                          |
|---------------|-------------------------------------|
| Armazenamento | AWS S3 + Delta Lake                 |
| Processamento | Databricks + PySpark                |
| Governança    | Unity Catalog                       |
| Segurança     | AWS IAM + Storage Credential        |
| CI/CD         | GitHub Actions                      |
| Linguagens    | Python / SQL                        |

### Estrutura do Data Lake no S3

O bucket central do projeto foi organizado da seguinte forma:

```text
s3://ifood-case-data-quality/
├── raw-data/
├── landing-data/
├── trusted-data/
├── rejected-data/
└── consumption-data/
```

---

## A Fundação: Infraestrutura AWS e Unity Catalog

Com a arquitetura definida, o próximo passo foi construir a infraestrutura que conecta o Databricks ao S3 de forma segura, sem nenhuma chave de acesso exposta no código.

### Passo 1 — IAM Policy

Foi criada uma policy de acesso granular ao bucket `ifood-case-data-quality`, separando permissões de leitura do bucket das permissões de manipulação de objetos:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BucketAccess",
      "Effect": "Allow",
      "Action": ["s3:ListBucket", "s3:GetBucketLocation"],
      "Resource": "arn:aws:s3:::ifood-case-data-quality"
    },
    {
      "Sid": "ObjectAccess",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": [
        "arn:aws:s3:::ifood-case-data-quality/raw-data/*",
        "arn:aws:s3:::ifood-case-data-quality/landing-data/*",
        "arn:aws:s3:::ifood-case-data-quality/trusted-data/*",
        "arn:aws:s3:::ifood-case-data-quality/rejected-data/*",
        "arn:aws:s3:::ifood-case-data-quality/consumption-data/*"
      ]
    }
  ]
}
```

### Passo 2 — IAM Role

Foi criada a role `ifood-databricks-case` para ser assumida pelo Unity Catalog do Databricks:

```text
ARN: arn:aws:iam::511417195220:role/ifood-databricks-case
```

A **trust relationship** foi configurada com o External ID gerado pelo Databricks, garantindo que apenas o Unity Catalog autorizado pode assumir a role:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": [
          "arn:aws:iam::414351767826:role/unity-catalog-prod-UCMasterRole-14S5ZJVKOTYTL",
          "arn:aws:iam::511417195220:role/ifood-databricks-case"
        ]
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "874cd2c1-178c-43cb-aac6-decabb1744a2"
        }
      }
    }
  ]
}
```

### Passo 3 — Storage Credential e Unity Catalog

Com a role criada, foi registrada a Storage Credential no Databricks:

```sql
CREATE STORAGE CREDENTIAL ifood_s3_credential
WITH AWS_ROLE = 'arn:aws:iam::511417195220:role/ifood-databricks-case';
```

Em seguida, foram criados o catálogo e os schemas que refletem as camadas da arquitetura:

```sql
CREATE CATALOG IF NOT EXISTS ifood;

CREATE SCHEMA IF NOT EXISTS ifood.landing;
CREATE SCHEMA IF NOT EXISTS ifood.trusted;
CREATE SCHEMA IF NOT EXISTS ifood.rejected;
CREATE SCHEMA IF NOT EXISTS ifood.consumption;
```

### Passo 4 — External Locations

Por fim, foram criadas as External Locations, o elo entre o Unity Catalog e os caminhos no S3:

```sql
CREATE EXTERNAL LOCATION ifood_landing_location
URL 's3://ifood-case-data-quality/landing-data/'
WITH (STORAGE CREDENTIAL ifood_s3_credential);

CREATE EXTERNAL LOCATION ifood_trusted_location
URL 's3://ifood-case-data-quality/trusted-data/'
WITH (STORAGE CREDENTIAL ifood_s3_credential);

CREATE EXTERNAL LOCATION ifood_rejected_location
URL 's3://ifood-case-data-quality/rejected-data/'
WITH (STORAGE CREDENTIAL ifood_s3_credential);

CREATE EXTERNAL LOCATION ifood_consumption_location
URL 's3://ifood-case-data-quality/consumption-data/'
WITH (STORAGE CREDENTIAL ifood_s3_credential);
```

O fluxo de autenticação completo ficou assim:

```text
Databricks Notebook
↓
Unity Catalog
↓
External Location
↓
Storage Credential
↓
IAM Role
↓
AWS S3
```

---

## A Esteira: CI/CD com GitHub Actions

Com a infraestrutura pronta, foi implementado um fluxo de CI/CD para garantir que qualquer alteração no código passe por validação antes de chegar em produção.

### Arquitetura do CI/CD

```text
GitHub
↓
GitHub Actions
↓
AWS
├── S3
├── IAM
└── Databricks
↓
Delta Lake
↓
Unity Catalog
```

### O Workflow

A cada push na branch `main`, o pipeline é acionado automaticamente:

```yaml
name: databricks-pipeline

on:
  push:
    branches:
      - main

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run tests
        run: pytest tests/

      - name: Deploy scripts
        run: echo "Deploy pipeline"
```

### Benefícios do CI/CD

- Redução de erros manuais
- Maior confiabilidade e reprodutibilidade
- Padronização dos processos de deploy
- Rastreabilidade de todas as alterações
- Escalabilidade operacional
- Acesso ao S3 sem Access Keys expostas no código

---

## A Pipeline de Dados

Com a infraestrutura e o CI/CD operando, o dado começa sua jornada.

### Dados Utilizados

Foram utilizados datasets públicos do **NYC TLC (Taxi & Limousine Commission)**:

- **Yellow Taxi** — corridas na cidade de Nova York
- **Green Taxi** — corridas em bairros periféricos e fora de Manhattan

Os dados incluem: data/hora de pickup e dropoff, distância, quantidade de passageiros, tipo de pagamento, valores monetários e localização de origem/destino.

---

### Camada RAW — O Dado Bruto

A camada RAW é o ponto de entrada. Os dados chegam exatamente como foram fornecidos pela fonte — sem qualquer tratamento, validação ou transformação. É a memória histórica imutável do pipeline.

---

### Camada LANDING — Rastreabilidade

Na camada LANDING, os dados ganham identidade. São adicionados metadados essenciais para rastreabilidade:

- `id_data` — identificador único do registro
- `year` e `month` — particionamento temporal
- `origem_dataset` — indica se o dado veio do Yellow ou Green Taxi

**Padronização de colunas**

Os dois datasets tinham nomenclaturas diferentes para as mesmas informações. Foi criado um modelo canônico:

| Dataset     | Original                  | Padronizado        |
|-------------|---------------------------|--------------------|
| Yellow Taxi | `tpep_pickup_datetime`    | `pickup_datetime`  |
| Yellow Taxi | `tpep_dropoff_datetime`   | `dropoff_datetime` |
| Green Taxi  | `lpep_pickup_datetime`    | `pickup_datetime`  |
| Green Taxi  | `lpep_dropoff_datetime`   | `dropoff_datetime` |

Exemplo de padronização:

```python
df_green = (
    df_green
    .withColumnRenamed("lpep_pickup_datetime", "pickup_datetime")
    .withColumnRenamed("lpep_dropoff_datetime", "dropoff_datetime")
)
```

Escrita na camada LANDING:

```python
df.write \
    .format("delta") \
    .mode("append") \
    .partitionBy("year", "month") \
    .save("s3://ifood-case-data-quality/landing-data/green_taxi/")
```

Registro no Unity Catalog:

```sql
CREATE TABLE IF NOT EXISTS ifood.landing.green_taxi
USING DELTA
LOCATION 's3://ifood-case-data-quality/landing-data/green_taxi/';
```

---

### Validações de Qualidade

Com os dados padronizados, cada registro passa por um conjunto de validações baseadas nos **Data Dictionaries oficiais do NYC TLC**:

| Validação                    | Regra                                          |
|------------------------------|------------------------------------------------|
| VendorID válido              | `col("VendorID").isin([1,2,6,7])`              |
| Pickup antes do Dropoff      | `col("pickup_datetime") < col("dropoff_datetime")` |
| Passageiros > 0              | `col("passenger_count") > 0`                   |
| Distância > 0                | `col("trip_distance") > 0`                     |
| Tipo de pagamento válido     | `col("payment_type").isin([0,1,2,3,4,5,6])`   |
| Valores monetários válidos   | `col("fare_amount") >= 0`                      |

**Estratégia de captura de erros — `erro_concat`**

Em vez de acumular todos os erros de um registro, foi adotada uma abordagem que captura o **primeiro erro encontrado**, tornando a rastreabilidade mais objetiva:

```python
for condicao, codigo_erro in condicoes_erro:
    erro_col = F.when(
        erro_col == "0",
        F.when(condicao, codigo_erro).otherwise(erro_col)
    ).otherwise(erro_col)

df_validado = df.withColumn("erro_concat", erro_col)
```

- A coluna começa com `"0"` — sem erros.
- Cada condição é avaliada em sequência.
- Ao encontrar o primeiro problema, o código do erro é gravado e as validações seguintes não sobrescrevem.

---

### Camada TRUSTED — Dados Confiáveis

Apenas os registros que passaram em todas as validações chegam até aqui. São dados padronizados, rastreados e prontos para consumo analítico.

```python
df_trusted.write \
    .format("delta") \
    .mode("append") \
    .partitionBy("year", "month") \
    .save("s3://ifood-case-data-quality/trusted-data/green_taxi/")
```

```sql
CREATE TABLE IF NOT EXISTS ifood.trusted.green_taxi
USING DELTA
LOCATION 's3://ifood-case-data-quality/trusted-data/green_taxi/';
```

---

### Camada REJECTED — Dados Inválidos

Os registros que falharam nas validações são centralizados na camada REJECTED, com todas as informações necessárias para investigação e reprocessamento:

```text
id_data        → identificador do registro original
erro_concat    → código do primeiro erro encontrado
origem_dataset → fonte do dado (yellow/green)
```

```python
df_rejected.write \
    .format("delta") \
    .mode("append") \
    .save("s3://ifood-case-data-quality/rejected-data/")
```

```sql
CREATE TABLE IF NOT EXISTS ifood.rejected.rejected_data
USING DELTA
LOCATION 's3://ifood-case-data-quality/rejected-data/';
```

---

## O Destino: Camada de Consumo

A jornada culmina na camada de consumo, onde Yellow Taxi e Green Taxi se unem em uma visão analítica unificada.

### União dos Datasets

```python
df_consumption = df_yellow.unionByName(df_green)
```

### Escrita e Registro

```python
df_consumption.write \
    .format("delta") \
    .mode("overwrite") \
    .save("s3://ifood-case-data-quality/consumption-data/taxi/")
```

```sql
CREATE TABLE IF NOT EXISTS ifood.consumption.taxi
USING DELTA
LOCATION 's3://ifood-case-data-quality/consumption-data/taxi/';
```

### Consumindo os Dados

A camada de consumo suporta tanto SQL quanto PySpark:

**SQL**
```sql
SELECT *
FROM ifood.consumption.taxi
LIMIT 10;
```

**PySpark**
```python
df = spark.table("ifood.consumption.taxi")
display(df)
```

---

## Estrutura Final

```text
ifood/
├── landing/      → dados rastreados
├── trusted/      → dados válidos
├── rejected/     → dados inválidos com motivo
└── consumption/  → visão unificada para análise
```

### Benefícios da Arquitetura

| Pilar              | O que entrega                                      |
|--------------------|----------------------------------------------------|
| Governança         | Unity Catalog centraliza acesso e metadados        |
| Rastreabilidade    | Data Lineage do raw ao consumption                 |
| Qualidade          | Validações baseadas em dicionário oficial          |
| Escalabilidade     | Delta Lake + S3 com particionamento                |
| Consumo híbrido    | SQL e PySpark na mesma camada                      |
| Segurança          | IAM sem Access Keys expostas                       |
| Automação          | CI/CD com GitHub Actions                           |