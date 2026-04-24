#!/bin/bash
export PATH="/Users/craigrobinson/.nvm/versions/node/v20.20.2/bin:$PATH"
exec pnpm --filter @mcu/web dev
