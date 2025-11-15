# Data Analysis - Pattern Discovery & Synonym Generation

This folder contains scripts for discovering unit patterns in the Neo4j product database and generating Lucene synonym files for improved search matching.

## Problem Statement

Users search for welding equipment using various unit formats:
- **Amperage**: "500A", "500 A", "500 Amps", "500 Ampere", "500 Ampères"
- **Measurements**: "30mm", "30 mm", "30.0 mm"
- **And 50-100+ other unit variations across multiple languages**

Without normalization, different formats return different results, causing poor user experience.

## Solution: Lucene Synonym Mapping

Instead of modifying application code for every variation, we:
1. **Discover** all unit patterns in the database
2. **Group** similar units into synonym categories
3. **Configure** Neo4j Lucene with synonym file
4. **Let Neo4j** handle all variations automatically

**Benefits**:
- ✅ No application code changes
- ✅ Handles 100+ patterns automatically
- ✅ Scalable and maintainable
- ✅ One-time configuration

---

## Scripts

### 1. `discover_patterns.py`

**Purpose**: Scan Neo4j database to discover all number+unit patterns

**Usage**:
```bash
cd data_analysis
python discover_patterns.py
```

**Output**: `results/discovered_patterns.json`

**What it does**:
- Connects to Neo4j database
- Queries all Product nodes
- Extracts patterns using regex: `\d+(?:\.\d+)?\s*[A-Za-z°%]+`
- Counts frequency of each unit
- Saves results to JSON file

**Example Output**:
```json
{
  "patterns": [
    {"unit": "a", "count": 342, "examples": ["500A", "300 A"]},
    {"unit": "mm", "count": 289, "examples": ["30mm", "38 mm"]},
    ...
  ]
}
```

---

### 2. `generate_synonyms.py`

**Purpose**: Group discovered patterns into synonym categories

**Usage**:
```bash
python generate_synonyms.py
```

**Input**: `results/discovered_patterns.json`
**Output**:
- `results/welding-synonyms.txt` (Lucene synonym file)
- `results/synonym_groups.json` (Structured groups)

**What it does**:
- Loads discovered patterns
- Classifies units into categories (amperage, voltage, length, etc.)
- Generates Lucene synonym file
- Flags uncategorized units for manual review

**Example Output** (welding-synonyms.txt):
```
# AMPERAGE
a, amp, amps, ampere, amperes, ampère, ampères

# VOLTAGE
v, volt, volts

# LENGTH_MM
mm, millimeter, millimeters, millimetre, millimetres
```

---

### 3. `verify_neo4j_capabilities.py`

**Purpose**: Check if Neo4j supports custom analyzers

**Usage**:
```bash
python verify_neo4j_capabilities.py
```

**What it does**:
- Checks Neo4j version (requires 5.0+)
- Lists available Lucene analyzers
- Tests custom analyzer creation
- Generates compatibility report

**Possible Outcomes**:
- ✅ **Compatible** - Proceed with synonym approach
- ⚠️ **Partial** - Version supports it, but feature disabled (e.g., Neo4j Aura)
- ❌ **Not Compatible** - Version too old or feature unavailable

---

### 4. `test_synonyms.py`

**Purpose**: Validate synonym matching after configuration

**Prerequisites**:
- Custom analyzer created in Neo4j
- welding-synonyms.txt uploaded
- productIndex recreated with custom analyzer

**Usage**:
```bash
python test_synonyms.py
```

**What it does**:
- Tests multiple unit variations
- Verifies all variations return same results
- Reports success/failure for each test
- Exit code 0 if all tests pass

**Example Test**:
```
Amperage Variations
-------------------
'500A'       → 15 products (max score: 8.5)
'500 A'      → 15 products (max score: 8.5)
'500 Amps'   → 15 products (max score: 8.5)
✅ PASS: All variations returned 15 products
```

---

## Workflow

### Phase 1: Discovery (Run Now)

```bash
# 1. Discover patterns
python discover_patterns.py

# 2. Generate synonym file
python generate_synonyms.py

# 3. Review output
cat results/welding-synonyms.txt

# 4. Check Neo4j compatibility
python verify_neo4j_capabilities.py
```

### Phase 2: Neo4j Configuration (After Discovery)

**If Neo4j Compatible** (version 5.0+, custom analyzers supported):

```cypher
-- 1. Upload welding-synonyms.txt to Neo4j import directory

-- 2. Create custom analyzer
CALL db.index.fulltext.createAnalyzer('weldingAnalyzer', {
  tokenizer: 'standard',
  filters: [
    'lowercase',
    'word_delimiter_graph',
    {
      name: 'synonym',
      config: {
        synonyms_path: 'welding-synonyms.txt',
        expand: true
      }
    },
    'asciifolding'
  ]
});

-- 3. Drop existing index
DROP INDEX productIndex IF EXISTS;

-- 4. Create index with custom analyzer
CREATE FULLTEXT INDEX productIndex
FOR (p:Product)
ON EACH [p.item_name, p.description_ruleset, p.gin, p.category]
OPTIONS {
  indexConfig: {
    `fulltext.analyzer`: 'weldingAnalyzer',
    `fulltext.eventually_consistent`: 'true'
  }
};

-- 5. Wait for index population (5-10 minutes)
-- Check status:
CALL db.index.fulltext.queryNodes('productIndex', '*')
YIELD node
RETURN count(node) as indexed_count;
```

### Phase 3: Testing & Validation

```bash
# Test synonym matching
python test_synonyms.py

# If all tests pass:
# ✅ Synonyms are working correctly
# ✅ No application code changes needed
# ✅ Ready for production
```

---

## File Structure

```
data_analysis/
├── README.md                          # This file
├── discover_patterns.py               # Pattern discovery script
├── generate_synonyms.py               # Synonym generation script
├── verify_neo4j_capabilities.py       # Compatibility checker
├── test_synonyms.py                   # Synonym validation tests
├── .gitignore                         # Ignore results/
└── results/                           # Output directory (gitignored)
    ├── discovered_patterns.json       # Raw patterns from DB
    ├── synonym_groups.json            # Grouped synonyms
    └── welding-synonyms.txt           # Lucene synonym file
```

---

## Troubleshooting

### Issue: "Neo4j credentials not found"
**Solution**: Ensure `src/backend/.env` exists with:
```
NEO4J_URI=neo4j+ssc://xxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

### Issue: "Custom analyzers not supported"
**Cause**: Neo4j Aura (cloud) may restrict this feature

**Solutions**:
1. Migrate to self-hosted Neo4j
2. Fall back to application-level normalization
3. Contact Neo4j support for Aura feature access

### Issue: "Synonym tests failing"
**Debug Steps**:
1. Verify custom analyzer exists: `CALL db.index.fulltext.listAvailableAnalyzers()`
2. Check index configuration: `SHOW INDEXES`
3. Verify synonym file uploaded correctly
4. Rebuild index if needed

---

## Next Steps After Completion

1. **Review** `results/welding-synonyms.txt` - manually verify synonym groupings
2. **Get domain expert approval** - ensure technical accuracy
3. **Upload** to Neo4j and configure custom analyzer
4. **Test** thoroughly before production deployment
5. **Monitor** search quality and add new synonyms as needed
6. **Update quarterly** - run discovery to find new patterns

---

## Performance Notes

- **Pattern Discovery**: 2-5 minutes for ~1500 products
- **Synonym Generation**: < 1 minute
- **Neo4j Index Rebuild**: 5-10 minutes (one-time)
- **Query Performance**: No overhead (analysis at index time)

---

## Dependencies

- Python 3.11+
- neo4j Python driver (installed in src/backend/venv)
- Access to Neo4j database
- No additional packages needed

---

## Support

For questions or issues:
1. Check this README
2. Review script output and error messages
3. Consult Neo4j documentation for custom analyzers
4. Check `src/backend/docs/` for related documentation

---

## Version History

- **v1.0** (2025-01-08) - Initial release
  - Pattern discovery
  - Synonym generation
  - Neo4j compatibility checking
  - Test suite

---

**Last Updated**: 2025-01-08
