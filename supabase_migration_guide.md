# Supabase Cloud to On-Prem Server Migration Guide
This document outlines the official, 100% reliable method for migrating your database from Supabase Cloud to your self-hosted on-premise instance. Since Chatbot KB documents are parsed directly into text columns, no external physical storage bucket migration is required.

---

## Prerequisites
1. **Cloud Connection String**: Navigate to your *Supabase Cloud Dashboard -> Project Settings -> Database*. Copy the **Direct Connection String** (not the transaction pooler) and replace `[YOUR-PASSWORD]` with your actual password.
2. **Docker Container Name**: Find the exact name of your local self-hosted PostgreSQL Docker container (typically `supabase_db` or `supabase-db`). You can check this by running `docker ps` on your server.
3. **Network Access**: Ensure your server can successfully reach out to the internet to connect to Supabase Cloud.

---

## Step 1: Install the Supabase CLI on your On-Prem Server
Log into your server via SSH and execute the following commands to install the standalone standalone binary:

```bash
# Download and install the CLI binary
curl -fsSL https://raw.githubusercontent.com/supabase/cli/main/install.sh | sh

# Add the CLI binary path to your system environment variables
export PATH=$PATH:$HOME/.supabase/bin
```

To verify the installation succeeded, run:
```bash
supabase --version
```

---

## Step 2: Back Up the Cloud Database
Create an isolated backup directory on the server to pull down the cloud snapshots. We split the database export into **Roles**, **Schema**, and **Data** components to prevent dependency errors during import.

```bash
# Create and move to backup folder
mkdir supabase_migration && cd supabase_migration

# 1. Export Roles (Database users, Row-Level Security policies, and permissions)
supabase db dump --db-url "YOUR_CLOUD_DIRECT_CONNECTION_STRING" -f roles.sql --role-only

# 2. Export Schema (Table structures, indexes, extensions, functions, and triggers)
supabase db dump --db-url "YOUR_CLOUD_DIRECT_CONNECTION_STRING" -f schema.sql

# 3. Export Data (Actual text rows, chunks, document contents, and metadata tables)
supabase db dump --db-url "YOUR_CLOUD_DIRECT_CONNECTION_STRING" -f data.sql --use-copy --data-only
```

---

## Step 3: Restore Data to Your Local Docker DB Container
Since the CLI is running directly on the host server, you can stream the `.sql` backup files directly into the active local database Docker container. 

*Crucial Optimization: We temporarily alter the `session_replication_role` to `replica`. This completely bypasses foreign key checks and custom triggers while inserting data, eliminating out-of-order dependency errors.*

Execute the following three restore operations in sequence:

```bash
# 1. Import all database users, roles, and structural security permissions
docker exec -i supabase_db psql -U postgres -d postgres < roles.sql

# 2. Import your relational table definitions, HNSW vector indexes, and types
docker exec -i supabase_db psql -U postgres -d postgres < schema.sql

# 3. Import parsed text and vector chunk contents safely as a replica
(echo "SET session_replication_role = replica;"; cat data.sql) | docker exec -i supabase_db psql -U postgres -d postgres
```

---

## Step 4: Post-Migration Validation
Log into your self-hosted instance (via your on-prem Studio Dashboard or a `psql` console) and check that your row counts perfectly match your cloud footprint:

```sql
-- Verify text records and chunk counts
SELECT count(*) FROM public.docs;
SELECT count(*) FROM public.chunks;
```

---
*Disclaimer: This file is dynamically generated for migration workflows. Always ensure a secondary backup is retained prior to modifying live local databases.*
