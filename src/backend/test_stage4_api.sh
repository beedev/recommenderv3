#!/bin/bash
#
# STAGE 4 Remote Search Debug Test via API
# Tests complete flow with user's actual G INs through the API
#
# User's Test Data:
# - PowerSource: Warrior 500i CC/CV 380 - 415V (GIN: 0465350883)
# - Feeder: Robust Feed Pro Water Cooled (GIN: 0445800881)
# - Cooler: Cool 2 (GIN: 0465427880)

set -e

API_BASE="http://localhost:8000"

echo "===================================================================================================="
echo "STAGE 4 REMOTE SEARCH DEBUG TEST (via API)"
echo "===================================================================================================="
echo ""

# Start fresh session
echo "Creating new session..."
SESSION_RESPONSE=$(curl -s -X POST "$API_BASE/api/v1/configurator/message" \
  -H "Content-Type: application/json" \
  -d '{"message": "I need a power source", "language": "en"}')

SESSION_ID=$(echo "$SESSION_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['session_id'])")
echo "✅ Session ID: $SESSION_ID"
echo ""

# Step 1: Select PowerSource
echo "===================================================================================================="
echo "STEP 1: SELECT POWERSOURCE (0465350883)"
echo "===================================================================================================="
curl -s -X POST "$API_BASE/api/v1/configurator/select" \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"gin\": \"0465350883\",
    \"product_data\": {
      \"gin\": \"0465350883\",
      \"name\": \"Warrior 500i CC/CV 380 - 415V\",
      \"category\": \"PowerSource\"
    },
    \"language\": \"en\"
  }" | python3 -m json.tool | grep -E "(current_state|PowerSource|Feeder|message)" | head -10

echo ""

# Step 2: Select Feeder
echo "===================================================================================================="
echo "STEP 2: SELECT FEEDER (0445800881)"
echo "===================================================================================================="
curl -s -X POST "$API_BASE/api/v1/configurator/select" \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"gin\": \"0445800881\",
    \"product_data\": {
      \"gin\": \"0445800881\",
      \"name\": \"Robust Feed Pro Water Cooled\",
      \"category\": \"Feeder\"
    },
    \"language\": \"en\"
  }" | python3 -m json.tool | grep -E "(current_state|PowerSource|Feeder|message)" | head -10

echo ""

# Step 3: Select Cooler
echo "===================================================================================================="
echo "STEP 3: SELECT COOLER (0465427880)"
echo "===================================================================================================="
curl -s -X POST "$API_BASE/api/v1/configurator/select" \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"gin\": \"0465427880\",
    \"product_data\": {
      \"gin\": \"0465427880\",
      \"name\": \"Cool 2\",
      \"category\": \"Cooler\"
    },
    \"language\": \"en\"
  }" | python3 -m json.tool | grep -E "(current_state|PowerSource|Feeder|Cooler|message)" | head -10

echo ""

# Step 4: Get current state to see if we're at FeederAccessories
echo "===================================================================================================="
echo "STEP 4: CHECK CURRENT STATE"
echo "===================================================================================================="
STATE_RESPONSE=$(curl -s -X GET "$API_BASE/api/v1/configurator/state/$SESSION_ID")
CURRENT_STATE=$(echo "$STATE_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['current_state'])")
echo "Current State: $CURRENT_STATE"

if [ "$CURRENT_STATE" = "feeder_accessories_selection" ]; then
    echo ""
    echo "✅ At FeederAccessories state - will select one to trigger STAGE 4"
    echo ""

    # Get first feeder accessory
    PRODUCTS=$(echo "$STATE_RESPONSE" | python3 -c "import sys, json; products = json.load(sys.stdin).get('products', []); print(json.dumps(products[0]) if products else '{}')")
    FIRST_GIN=$(echo "$PRODUCTS" | python3 -c "import sys, json; print(json.load(sys.stdin).get('gin', ''))")

    if [ -n "$FIRST_GIN" ]; then
        echo "Selecting FeederAccessory: $FIRST_GIN"
        echo ""
        echo "===================================================================================================="
        echo "STEP 5: SELECT FEEDER ACCESSORY (TRIGGER STAGE 4)"
        echo "===================================================================================================="
        STAGE4_RESPONSE=$(curl -s -X POST "$API_BASE/api/v1/configurator/select" \
          -H "Content-Type: application/json" \
          -d "{
            \"session_id\": \"$SESSION_ID\",
            \"gin\": \"$FIRST_GIN\",
            \"product_data\": $PRODUCTS,
            \"language\": \"en\"
          }")

        NEW_STATE=$(echo "$STAGE4_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin)['current_state'])")
        PRODUCT_COUNT=$(echo "$STAGE4_RESPONSE" | python3 -c "import sys, json; print(len(json.load(sys.stdin).get('products', [])))")

        echo "New State: $NEW_STATE"
        echo "Products Found: $PRODUCT_COUNT"
        echo ""

        if [ "$NEW_STATE" = "remote_selection" ]; then
            if [ "$PRODUCT_COUNT" = "0" ]; then
                echo "❌ ERROR: Remote search returned 0 products (expected 4)"
                echo ""
                echo "🔍 CHECK SERVER LOGS FOR DEBUG OUTPUT:"
                echo "   grep '🔍' server.log | tail -50"
            else
                echo "✅ SUCCESS: Remote search returned $PRODUCT_COUNT products"
            fi
        else
            echo "❌ ERROR: Did not advance to Remote selection (state: $NEW_STATE)"
        fi
    else
        echo "❌ ERROR: No FeederAccessories found"
    fi
else
    echo "❌ ERROR: Not at FeederAccessories state (current: $CURRENT_STATE)"
fi

echo ""
echo "===================================================================================================="
echo "TEST COMPLETE - Check server.log for detailed debug output"
echo "View debug logs: grep '🔍' server.log | tail -100"
echo "===================================================================================================="
