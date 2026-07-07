#!/bin/bash
# Destroy all deployed resources.
set -e

echo "============================================"
echo "  DVI Narration Pipeline - Teardown"
echo "============================================"
echo ""
echo "This will DELETE all resources created by this sample."
echo "Press Ctrl+C to cancel, or wait 5 seconds to continue..."
sleep 5

echo ""
echo "Destroying CDK stacks..."
npx cdk destroy --all --force

echo ""
echo "Teardown complete. All resources have been deleted."
