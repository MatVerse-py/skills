-- webhook.lua
-- Endpoint exemplo: /api/v1/webhook/payment
-- Mesmo protocolo do payment: HMAC + nonce + exp.

local cjson = require("cjson.safe")
local autoheal = require("autoheal_client")
local hmac = require("hmac")

ngx.req.read_body()
local body = ngx.req.get_body_data() or ""

local sig = ngx.req.get_headers()["x-signature"]
local nonce = ngx.req.get_headers()["x-nonce"]
local exp = ngx.req.get_headers()["x-expires"]

local secret, err = autoheal.get_secret("payment_webhook_secret")
if not secret then
  ngx.status = 503
  ngx.say(cjson.encode({ ok=false, error="autoheal_unavailable", detail=err }))
  return
end

local ok, verr = hmac.verify(secret, body, nonce, exp, sig)
if not ok then
  ngx.status = 401
  ngx.say(cjson.encode({ ok=false, error="auth_failed", detail=verr }))
  return
end

local event, perr = cjson.decode(body)
if not event then
  ngx.status = 400
  ngx.say(cjson.encode({ ok=false, error="bad_json", detail=perr }))
  return
end

ngx.status = 200
ngx.say(cjson.encode({ ok=true, status="webhook_ok", echo=event }))
