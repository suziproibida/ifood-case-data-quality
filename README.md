# Projeto Lakehouse - Data Quality NYC Taxi

## Objetivo

Este projeto tem como objetivo construir uma arquitetura moderna de Data Lakehouse utilizando AWS S3, Databricks, Unity Catalog e PySpark para ingestão, padronização, validação e consumo de dados de corridas de táxi da cidade de Nova York.

A solução foi construída utilizando múltiplas camadas de dados para garantir:

* Governança
* Rastreabilidade
* Qualidade de Dados
* Escalabilidade
* Consumo SQL e PySpark
* Arquitetura Lakehouse

---

# Arquitetura

```text
RAW
↓
LANDING
↓
VALIDAÇÕES
├── TRUSTED
└── REJECTED
↓
CONSUMPTION
```

---

# Tecnologias Utilizadas

* AWS S3
* Databricks
* Unity Catalog
* PySpark
* Delta Lake
* SQL
* AWS IAM
* Storage Credential
* External Locations

---

# Estrutura do Data Lake

```text
s3://ifood-case-data-quality/

├── raw-data/
├── landing-data/
├── trusted-data/
├── rejected-data/
├── consumption-data/
└── audit-data/
```

---

# Configuração AWS IAM + Unity Catalog

## Criação da IAM Policy

Foi criada uma policy de acesso ao bucket S3 utilizado no projeto.

Bucket:

```text
ifood-case-data-quality
```

Policy utilizada:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BucketAccess",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": "arn:aws:s3:::ifood-case-data-quality"
    },
    {
      "Sid": "ObjectAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::ifood-case-data-quality/raw-data/*",
        "arn:aws:s3:::ifood-case-data-quality/landing-data/*",
        "arn:aws:s3:::ifood-case-data-quality/trusted-data/*",
        "arn:aws:s3:::ifood-case-data-quality/rejected-data/*",
        "arn:aws:s3:::ifood-case-data-quality/consumption-data/*",
        "arn:aws:s3:::ifood-case-data-quality/audit-data/*"
      ]
    }
  ]
}
```

---

# Criação da IAM Role

Foi criada uma IAM Role para ser assumida pelo Databricks Unity Catalog.

Nome da role:

```text
ifood-databricks-case
```

ARN da role:

```text
arn:aws:iam::511417195220:role/ifood-databricks-case
```

---

# Trust Relationship

Após a criação da Storage Credential no Databricks, foi gerado um External ID utilizado na configuração da trust relationship.

Trust Policy utilizada:

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

---

# Criação da Storage Credential

```sql
CREATE STORAGE CREDENTIAL ifood_s3_credential
WITH AWS_ROLE = 'arn:aws:iam::511417195220:role/ifood-databricks-case';
```

---

# Unity Catalog

## Criação do catálogo

```sql
CREATE CATALOG IF NOT EXISTS ifood;
```

---

## Criação dos schemas

```sql
CREATE SCHEMA IF NOT EXISTS ifood.raw;

CREATE SCHEMA IF NOT EXISTS ifood.landing;

CREATE SCHEMA IF NOT EXISTS ifood.trusted;

CREATE SCHEMA IF NOT EXISTS ifood.rejected;

CREATE SCHEMA IF NOT EXISTS ifood.consumption;

CREATE SCHEMA IF NOT EXISTS ifood.audit;
```

---

# Criação das External Locations

## Landing

```sql
CREATE EXTERNAL LOCATION ifood_landing_location
URL 's3://ifood-case-data-quality/landing-data/'
WITH (STORAGE CREDENTIAL ifood_s3_credential);
```

## Trusted

```sql
CREATE EXTERNAL LOCATION ifood_trusted_location
URL 's3://ifood-case-data-quality/trusted-data/'
WITH (STORAGE CREDENTIAL ifood_s3_credential);
```

## Rejected

```sql
CREATE EXTERNAL LOCATION ifood_rejected_location
URL 's3://ifood-case-data-quality/rejected-data/'
WITH (STORAGE CREDENTIAL ifood_s3_credential);
```

## Consumption

```sql
CREATE EXTERNAL LOCATION ifood_consumption_location
URL 's3://ifood-case-data-quality/consumption-data/'
WITH (STORAGE CREDENTIAL ifood_s3_credential);
```

---

# Fluxo de Autenticação

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

# Dados Utilizados

Foram utilizados datasets públicos de corridas de táxi da cidade de Nova York (NYC TLC).

Tipos de datasets utilizados:

* Yellow Taxi
* Green Taxi
* FHV Taxi

Os dados incluem informações como:

* Data e hora de pickup/dropoff
* Distância da corrida
* Quantidade de passageiros
* Tipo de pagamento
* Valores monetários
* Localização de origem/destino
* Tipo de corrida

---

# Padronização dos Dados

Os datasets possuíam diferenças de nomenclatura entre colunas.

Exemplo:

```text
Yellow Taxi:
tpep_pickup_datetime

Green Taxi:
lpep_pickup_datetime
```

Foi criado um modelo canônico padronizando os nomes para:

```text
pickup_datetime
dropoff_datetime
```

Exemplo:

```python
df_green = (
    df_green
    .withColumnRenamed(
        "lpep_pickup_datetime",
        "pickup_datetime"
    )
    .withColumnRenamed(
        "lpep_dropoff_datetime",
        "dropoff_datetime"
    )
)
```

---

# Camada RAW

A camada RAW armazena os dados exatamente como recebidos da fonte.

Características:

* Sem tratamento
* Sem validações
* Dados brutos
* Persistência histórica

---

# Camada LANDING

A camada LANDING é responsável pela rastreabilidade dos dados.

Nesta etapa foram adicionados:

* id_data
* year
* month
* origem_dataset

Exemplo de escrita:

```python
df.write \
    .format("delta") \
    .mode("append") \
    .partitionBy("year", "month") \
    .save("s3://ifood-case-data-quality/landing-data/green_taxi/")
```

---

# Registro das tabelas no Unity Catalog

## Landing

```sql
CREATE TABLE IF NOT EXISTS ifood.landing.green_taxi
USING DELTA
LOCATION 's3://ifood-case-data-quality/landing-data/green_taxi/';
```

## Trusted

```sql
CREATE TABLE IF NOT EXISTS ifood.trusted.green_taxi
USING DELTA
LOCATION 's3://ifood-case-data-quality/trusted-data/green_taxi/';
```

## Rejected

```sql
CREATE TABLE IF NOT EXISTS ifood.rejected.rejected_data
USING DELTA
LOCATION 's3://ifood-case-data-quality/rejected-data/';
```

---

# Validações de Qualidade dos Dados

As validações foram construídas utilizando os Data Dictionaries oficiais do NYC TLC.

Principais validações:

## VendorID válido

```python
col("VendorID").isin([1,2,6,7])
```

## Pickup menor que Dropoff

```python
col("pickup_datetime") < col("dropoff_datetime")
```

## passenger_count maior que zero

```python
col("passenger_count") > 0
```

## trip_distance maior que zero

```python
col("trip_distance") > 0
```

## payment_type válido

```python
col("payment_type").isin([0,1,2,3,4,5,6])
```

## Valores monetários não negativos

```python
(col("fare_amount") >= 0)
```

---

# Construção da coluna erro_concat

A construção da coluna `erro_concat` foi implementada utilizando uma abordagem sequencial baseada em regras de validação.

Diferente de concatenação múltipla de erros, a estratégia adotada prioriza o primeiro erro encontrado para cada registro, permitindo rastrear de forma objetiva a principal inconsistência identificada durante o processo de qualidade de dados.

---

## Implementação Utilizada

```python id="4rckdr"
for condicao, codigo_erro in condicoes_erro:

    erro_col = F.when(
        erro_col == "0",
        F.when(condicao, codigo_erro).otherwise(erro_col)
    ).otherwise(erro_col)

df_validado = df.withColumn(
    "erro_concat",
    erro_col
)
```

---

## Funcionamento da Regra

A lógica funciona da seguinte forma:

* Inicialmente, a coluna `erro_col` recebe o valor `"0"` indicando ausência de erro.
* Cada condição de validação é avaliada sequencialmente.
* Quando uma condição inválida é encontrada:

  * o código do erro é atribuído à coluna `erro_concat`
  * as próximas validações deixam de alterar o registro
* O resultado final representa o primeiro erro identificado no dado.


---

# Camada TRUSTED

A camada TRUSTED armazena apenas registros válidos após todas as validações de qualidade.

Características:

* Dados confiáveis
* Dados padronizados
* Dados prontos para consumo analítico

Exemplo de escrita:

```python
df_trusted.write \
    .format("delta") \
    .mode("append") \
    .partitionBy("year", "month") \
    .save("s3://ifood-case-data-quality/trusted-data/green_taxi/")
```

---

# Camada REJECTED

A camada REJECTED centraliza os registros inválidos.

Estrutura:

```text
id_data
erro_concat
origem_dataset
dt_rejeicao
```

Exemplo:

```python
df_rejected.write \
    .format("delta") \
    .mode("append") \
    .save("s3://ifood-case-data-quality/rejected-data/")
```

---

# Camada CONSUMPTION

A camada CONSUMPTION possui visão unificada dos datasets.

Foi realizado o UNION dos datasets:

* Yellow Taxi
* Green Taxi
* FHV Taxi

Exemplo:

```python
df_consumption = (
    df_yellow
    .unionByName(df_green)
    .unionByName(df_fhv)
)
```

Escrita:

```python
df_consumption.write \
    .format("delta") \
    .mode("overwrite") \
    .save("s3://ifood-case-data-quality/consumption-data/taxi/")
```

Registro:

```sql
CREATE TABLE IF NOT EXISTS ifood.consumption.taxi
USING DELTA
LOCATION 's3://ifood-case-data-quality/consumption-data/taxi/';
```

---

# Consumo dos Dados

## SQL

```sql
SELECT *
FROM ifood.consumption.taxi
LIMIT 10;
```

## PySpark

```python
df = spark.table("ifood.consumption.taxi")

display(df)
```

---

# Benefícios da Arquitetura

* Arquitetura Lakehouse
* Governança centralizada
* Data Lineage
* Rastreabilidade
* Escalabilidade
* Reuso de código
* Data Quality
* Consumo híbrido SQL/PySpark
* Persistência em Delta Lake

---

# Estrutura Final do Projeto

```text
ifood
├── raw
├── landing
├── trusted
├── rejected
├── consumption
└── audit
```
