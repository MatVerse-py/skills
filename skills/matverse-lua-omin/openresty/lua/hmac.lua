-- hmac.lua
-- HMAC-SHA256 + anti-replay mínimo. Zero-ENV: segredo vem do AutoHeal.

local resty_hmac = require("resty.hmac")
local resty_str = require("resty.string")

local _M = {}

function _M.sign(secret, body, nonce, exp_s)
  local h = resty_hmac:new(secret, resty_hmac.ALGOS.SHA256)
  if not h then return nil, "hmac_init_failed" end
  h:update(body)
  h:update("|")
  h:update(nonce)
  h:update("|")
  h:update(tostring(exp_s))
  local digest = h:final()
  return resty_str.to_hex(digest), nil
end

function _M.verify(secret, body, nonce, exp_s, sig_hex)
  if not nonce or nonce == "" then return false, "missing_nonce" end
  if not exp_s then return false, "missing_exp" end

  local now = ngx.time()
  if tonumber(exp_s) < now then
    return false, "expired"
  end

  local expected, err = _M.sign(secret, body, nonce, exp_s)
  if not expected then
    return false, err
  end

  if expected ~= sig_hex then
    return false, "bad_signature"
  end

  return true, nil
end

return _M
