-- -- Script DDL para PostgreSQL (talent_bridge)

-- -- 1. Tabla de Empresas (Aislamiento Multi-tenant)
-- CREATE TABLE IF NOT EXISTS empresa (
--     empresa_id INT PRIMARY KEY,
--     nombre VARCHAR(100) NOT NULL
-- );

-- -- 2. Puntos de Venta
-- CREATE TABLE IF NOT EXISTS punto_venta (
--     punto_venta_id INT PRIMARY KEY,
--     empresa_id INT NOT NULL REFERENCES empresa(empresa_id),
--     nombre VARCHAR(100) NOT NULL,
--     ciudad VARCHAR(50) NOT NULL
-- );

-- -- 3. Asesores Comerciales
-- CREATE TABLE IF NOT EXISTS asesor (
--     asesor_id INT PRIMARY KEY,
--     empresa_id INT NOT NULL REFERENCES empresa(empresa_id),
--     punto_venta_id INT NOT NULL REFERENCES punto_venta(punto_venta_id),
--     nombre VARCHAR(100) NOT NULL,
--     capacidad_diaria INT NOT NULL
-- );

-- -- 4. Leads Consolidados, Enriquecidos por IA y Priorizados
-- CREATE TABLE IF NOT EXISTS lead (
--     lead_id VARCHAR(50) PRIMARY KEY,
--     empresa_id INT NOT NULL REFERENCES empresa(empresa_id),
--     punto_venta_id INT REFERENCES punto_venta(punto_venta_id),
    
--     -- Datos Limpios y Normalizados (CSV/JSON)
--     nombre_cliente VARCHAR(150),
--     telefono VARCHAR(20),
--     email VARCHAR(100),
--     ciudad VARCHAR(50),
--     canal VARCHAR(30),
--     fecha_registro TIMESTAMP WITH TIME ZONE,
    
--     -- Información Extraída con IA (conversaciones.json)
--     modelo_interes_extraido VARCHAR(100),
--     cuota_inicial_declarada NUMERIC(12, 2) DEFAULT 0.00,
--     forma_pago VARCHAR(30),
--     intencion_declarada VARCHAR(20),
--     objecion_principal VARCHAR(150),
--     pidio_cita_cotizacion BOOLEAN DEFAULT FALSE,
    
--     -- Scoring y Asignación de Gestión
--     score_prioridad NUMERIC(5, 2) DEFAULT 0.00,
--     temperatura VARCHAR(20) DEFAULT 'FRIO', -- 'CALIENTE', 'TIBIO', 'FRIO'
--     asesor_asociado_id INT REFERENCES asesor(asesor_id),
--     estado_gestion VARCHAR(50) DEFAULT 'Sin Gestión',
    
--     -- Auditoría
--     fecha_procesamiento TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
-- );

-- -- Índices para optimizar las consultas del Dashboard por Empresa
-- CREATE INDEX IF NOT EXISTS idx_lead_empresa ON lead(empresa_id);
-- CREATE INDEX IF NOT EXISTS idx_lead_score ON lead(score_prioridad DESC);