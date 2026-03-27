-- autoheal_client.lua
-- Cliente Zero-ENV via Unix socket para obter material efêmero do sidecar.
-- Fail-closed: qualquer erro => nil + msg.

local http = require("resty.http")

local _M = {}

local function new_httpc()
  local httpc = http.new()
  httpc:set_timeout(500) -- ms
  return httpc
end

function _M.get_secret(service)
  local httpc = new_httpc()
  -- Unix socket: /run/matverse/autoheal.sock
  local res, err = httpc:request_uri("http://unix:/run/matverse/autoheal.sock:/v1/secret", {
    method = "GET",
    query = { service = service },
    headers = { ["Accept"] = "application/json" },
  })

  if not res then
    return nil, "autoheal_unreachable: " .. (err or "")
  end

  if res.status ~= 200 then
    return nil, "autoheal_bad_status: " .. tostring(res.status)
  end

  local cjson = require("cjson.safe")
  local obj, jerr = cjson.decode(res.body)
  if not obj then
    return nil, "autoheal_bad_json: " .. (jerr or "")
  end

  if not obj.secret or type(obj.secret) ~= "string" then
    return nil, "autoheal_missing_secret"
  end

  return obj.secret, nil
end

return _M
