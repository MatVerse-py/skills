-- payment.lua
-- Endpoint exemplo: /api/v1/payment
-- Zero-ENV: segredo vem do sidecar AutoHeal (unix socket).
-- Fail-closed: qualquer falha => 401/503.

local cjson = require("cjson.safe")
local autoheal = require("autoheal_client")
local hmac = require("hmac")

ngx.req.read_body()
local body = ngx.req.get_body_data() or ""

local sig = ngx.req.get_headers()["x-signature"]
local nonce = ngx.req.get_headers()["x-nonce"]
local exp = ngx.req.get_headers()["x-expires"]

-- 1) kill-switch (opcional): sidecar pode expor /v1/status
-- (aqui omitido por simplicidade)

-- 2) obter segredo efêmero
local secret, err = autoheal.get_secret("payment_webhook_secret")
if not secret then
  ngx.status = 503
  ngx.say(cjson.encode({ ok=false, error="autoheal_unavailable", detail=err }))
  return
end

-- 3) verificar assinatura
local ok, verr = hmac.verify(secret, body, nonce, exp, sig)
if not ok then
  ngx.status = 401
  ngx.say(cjson.encode({ ok=false, error="auth_failed", detail=verr }))
  return
end

-- 4) parse payload
local payload, perr = cjson.decode(body)
if not payload then
  ngx.status = 400
  ngx.say(cjson.encode({ ok=false, error="bad_json", detail=perr }))
  return
end

-- 5) responder (aqui você integra seu motor real)
ngx.status = 200
ngx.say(cjson.encode({ ok=true, status="accepted", echo=payload }))
