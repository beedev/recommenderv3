// ============================================================================
// ESAB Recommender V2 - Neo4j Initialization Script
// Creates constraints, indexes, and basic schema for product graph database
// ============================================================================

// ==========================
// 1. Create Constraints
// ==========================

// PowerSource node constraints
CREATE CONSTRAINT power_source_gin_unique IF NOT EXISTS
FOR (ps:PowerSource) REQUIRE ps.gin IS UNIQUE;

CREATE CONSTRAINT power_source_name IF NOT EXISTS
FOR (ps:PowerSource) REQUIRE ps.name IS NOT NULL;

// Feeder node constraints
CREATE CONSTRAINT feeder_gin_unique IF NOT EXISTS
FOR (f:Feeder) REQUIRE f.gin IS UNIQUE;

CREATE CONSTRAINT feeder_name IF NOT EXISTS
FOR (f:Feeder) REQUIRE f.name IS NOT NULL;

// Cooler node constraints
CREATE CONSTRAINT cooler_gin_unique IF NOT EXISTS
FOR (c:Cooler) REQUIRE c.gin IS UNIQUE;

CREATE CONSTRAINT cooler_name IF NOT EXISTS
FOR (c:Cooler) REQUIRE c.name IS NOT NULL;

// Interconnector node constraints
CREATE CONSTRAINT interconnector_gin_unique IF NOT EXISTS
FOR (i:Interconnector) REQUIRE i.gin IS UNIQUE;

CREATE CONSTRAINT interconnector_name IF NOT EXISTS
FOR (i:Interconnector) REQUIRE i.name IS NOT NULL;

// Torch node constraints
CREATE CONSTRAINT torch_gin_unique IF NOT EXISTS
FOR (t:Torch) REQUIRE t.gin IS UNIQUE;

CREATE CONSTRAINT torch_name IF NOT EXISTS
FOR (t:Torch) REQUIRE t.name IS NOT NULL;

// Accessory node constraints
CREATE CONSTRAINT accessory_gin_unique IF NOT EXISTS
FOR (a:Accessory) REQUIRE a.gin IS UNIQUE;

CREATE CONSTRAINT accessory_name IF NOT EXISTS
FOR (a:Accessory) REQUIRE a.name IS NOT NULL;

// ==========================
// 2. Create Indexes
// ==========================

// Full-text search indexes for product names
CREATE FULLTEXT INDEX product_name_fulltext IF NOT EXISTS
FOR (n:PowerSource|Feeder|Cooler|Interconnector|Torch|Accessory)
ON EACH [n.name];

// Property indexes for common search fields
CREATE INDEX power_source_process IF NOT EXISTS
FOR (ps:PowerSource) ON (ps.process);

CREATE INDEX power_source_current IF NOT EXISTS
FOR (ps:PowerSource) ON (ps.current_output);

CREATE INDEX feeder_cooling_type IF NOT EXISTS
FOR (f:Feeder) ON (f.cooling_type);

CREATE INDEX torch_amperage IF NOT EXISTS
FOR (t:Torch) ON (t.amperage);

CREATE INDEX torch_cooling IF NOT EXISTS
FOR (t:Torch) ON (t.cooling);

CREATE INDEX accessory_category IF NOT EXISTS
FOR (a:Accessory) ON (a.category);

// Relationship indexes
CREATE INDEX compatible_with_index IF NOT EXISTS
FOR ()-[r:COMPATIBLE_WITH]-() ON (r.compatibility_type);

// ==========================
// 3. Verify Schema
// ==========================

// Show all constraints
SHOW CONSTRAINTS;

// Show all indexes
SHOW INDEXES;

// ==========================
// 4. Sample Data (Optional)
// ==========================

// Uncomment below to create sample product nodes for testing

/*
// Sample PowerSource
CREATE (ps:PowerSource {
    gin: "0446200880",
    name: "Aristo 500ix",
    process: "MIG (GMAW)",
    current_output: "500 A",
    cooling: "Water-cooled",
    duty_cycle: "100% @ 500A",
    created_at: datetime(),
    updated_at: datetime()
});

// Sample Feeder
CREATE (f:Feeder {
    gin: "0460460001",
    name: "RobustFeed",
    cooling_type: "Water-cooled",
    wire_diameter: "1.2mm - 1.6mm",
    motor_type: "4-roll drive",
    created_at: datetime(),
    updated_at: datetime()
});

// Sample compatibility relationship
MATCH (ps:PowerSource {gin: "0446200880"})
MATCH (f:Feeder {gin: "0460460001"})
CREATE (f)-[:COMPATIBLE_WITH {
    compatibility_type: "certified",
    notes: "Certified combination for MIG welding",
    created_at: datetime()
}]->(ps);
*/

// ==========================
// 5. Database Statistics
// ==========================

// Count nodes by label
MATCH (n:PowerSource) RETURN 'PowerSource' AS label, count(n) AS count
UNION
MATCH (n:Feeder) RETURN 'Feeder' AS label, count(n) AS count
UNION
MATCH (n:Cooler) RETURN 'Cooler' AS label, count(n) AS count
UNION
MATCH (n:Interconnector) RETURN 'Interconnector' AS label, count(n) AS count
UNION
MATCH (n:Torch) RETURN 'Torch' AS label, count(n) AS count
UNION
MATCH (n:Accessory) RETURN 'Accessory' AS label, count(n) AS count
ORDER BY label;

// Count compatibility relationships
MATCH ()-[r:COMPATIBLE_WITH]->()
RETURN 'COMPATIBLE_WITH' AS relationship, count(r) AS count;

// ==========================
// Initialization Complete
// ==========================
