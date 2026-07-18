local WS_URL = "ws://127.0.0.1:8081"
local RECONNECT_DELAY = 5
local CHUNK_SIZE = 128

local AssetService = game:GetService("AssetService")
local GuiService = game:GetService("GuiService")
local Players = game:GetService("Players")
local UserInputService = game:GetService("UserInputService")

if C2 and C2._running then return end
C2 = {}
C2._running = true
C2._dbg_idx = 0
C2.debug = function(msg)
    C2._dbg_idx = C2._dbg_idx + 1
    pcall(function()
        local old = ""
        local ok, data = pcall(readfile, "c2_log.txt")
        if ok then old = data end
        local lines = {}
        for line in old:gmatch("[^\n]+") do
            table.insert(lines, line)
        end
        while #lines > 200 do table.remove(lines, 1) end
        table.insert(lines, "[" .. C2._dbg_idx .. "] " .. tostring(msg))
        writefile("c2_log.txt", table.concat(lines, "\n"))
    end)
end
C2.browser_coords = function()
    if not C2.browser or not C2.browser.viewport then return end
    local vp = C2.browser.viewport
    if vp.AbsoluteSize.X <= 0 or vp.AbsoluteSize.Y <= 0 then return end
    local mp = UserInputService:GetMouseLocation()
    local rx = mp.X - vp.AbsolutePosition.X
    local ry = mp.Y - vp.AbsolutePosition.Y
    if rx < 0 or ry < 0 or rx > vp.AbsoluteSize.X or ry > vp.AbsoluteSize.Y then return end
    return math.floor(rx / vp.AbsoluteSize.X * C2.browser.width),
           math.floor(ry / vp.AbsoluteSize.Y * C2.browser.height)
end

C2.send = function(t)
    C2.debug("SEND: " .. game:GetService("HttpService"):JSONEncode(t))
    pcall(function() ws:Send(game:GetService("HttpService"):JSONEncode(t)) end)
end
C2.on_message = nil
C2.hidden_guis = {}
C2.hide_all_guis = function()
    C2.hidden_guis = {}
    if C2.current_gui and C2.current_gui.Enabled then
        C2.current_gui.Enabled = false
        table.insert(C2.hidden_guis, C2.current_gui)
    end
    for _, gui in ipairs(Players.LocalPlayer:WaitForChild("PlayerGui"):GetChildren()) do
        if gui:IsA("ScreenGui") and gui.Enabled and gui ~= (C2.browser and C2.browser.screen_gui) then
            gui.Enabled = false
            table.insert(C2.hidden_guis, gui)
        end
    end
end
C2.restore_hidden_guis = function()
    for _, gui in ipairs(C2.hidden_guis) do
        pcall(function() gui.Enabled = true end)
    end
    C2.hidden_guis = {}
end

C2.unload = function()
    C2.debug("UNLOAD called")
    C2.on_message = nil
    C2.restore_hidden_guis()
    C2.browser_shutdown()
    if C2.current_gui then
        C2.debug("UNLOAD: destroying GUI")
        pcall(function() C2.current_gui:Destroy() end)
        C2.current_gui = nil
    end
end

-- Browser streaming state
C2.browser = nil

function C2.browser_init()
    if C2.browser and C2.browser.active then
        C2.debug("browser_init: already active, recreating")
        C2.browser_shutdown()
    end
    C2.debug("browser_init")

    local screen_gui = Instance.new("ScreenGui")
    screen_gui.Name = "BrowserStream"
    screen_gui.DisplayOrder = 999
    screen_gui.IgnoreGuiInset = true
    screen_gui.ResetOnSpawn = false

    local frame = Instance.new("Frame")
    frame.Name = "BrowserViewport"
    frame.Size = UDim2.fromScale(1, 1)
    frame.BackgroundTransparency = 1
    frame.BorderSizePixel = 0
    frame.Position = UDim2.fromScale(0.5, 0.5)
    frame.AnchorPoint = Vector2.new(0.5, 0.5)

    local aspect = Instance.new("UIAspectRatioConstraint")
    aspect.Parent = frame

    local image = Instance.new("ImageButton")
    image.Name = "Screen"
    image.Size = UDim2.fromScale(1, 1)
    image.BackgroundTransparency = 1
    image.AutoButtonColor = false
    image.BorderSizePixel = 0
    image.Parent = frame

    local textbox = Instance.new("TextBox")
    textbox.Name = "KeyCapture"
    textbox.Size = UDim2.new(0, 0, 0, 0)
    textbox.Visible = false
    textbox.ClearTextOnFocus = true
    textbox.Parent = screen_gui

    frame.Parent = screen_gui
    screen_gui.Parent = Players.LocalPlayer:WaitForChild("PlayerGui")

    C2.browser = {
        active = true,
        editable_image = nil,
        image_label = image,
        viewport = frame,
        screen_gui = screen_gui,
        textbox = textbox,
        width = 0,
        height = 0,
        ready = false,
    }

    C2._last_mx = nil
    C2._last_my = nil

    image.MouseMoved:Connect(function(lx, ly)
        if not C2.browser.ready then return end
        local vp = C2.browser.viewport
        if vp.AbsoluteSize.X <= 0 or vp.AbsoluteSize.Y <= 0 then return end
        local mx = math.floor(lx / vp.AbsoluteSize.X * C2.browser.width)
        local my = math.floor(ly / vp.AbsoluteSize.Y * C2.browser.height)
        C2._last_mx = mx
        C2._last_my = my
        C2.debug("MOUSE moved: canvas(" .. lx .. "," .. ly .. ") -> browser(" .. mx .. "," .. my .. ") vp=" .. vp.AbsoluteSize.X .. "x" .. vp.AbsoluteSize.Y .. " bw=" .. C2.browser.width .. " bh=" .. C2.browser.height)
        C2.browser_send_mouse(C2._last_mx, C2._last_my, 0)
    end)

    local function do_click(ev_down, ev_up)
        if not C2.browser.ready then
            C2.debug("MOUSE click ignored: browser not ready")
            return
        end
        if C2._last_mx == nil then
            C2.debug("MOUSE click ignored: no last mouse pos")
            return
        end
        C2.debug("MOUSE click: down=" .. ev_down .. " up=" .. ev_up .. " at (" .. C2._last_mx .. "," .. C2._last_my .. ")")
        if ev_down == 1 then
            pcall(function() textbox:CaptureFocus() end)
        end
        C2.browser_send_mouse(C2._last_mx, C2._last_my, ev_down)
        task.wait(0.05)
        C2.browser_send_mouse(C2._last_mx, C2._last_my, ev_up)
    end

    image.MouseButton1Click:Connect(function() do_click(1, 3) end)
    image.MouseButton2Click:Connect(function() do_click(2, 4) end)

    textbox:GetPropertyChangedSignal("Text"):Connect(function()
        if not C2.browser.ready then return end
        local text = textbox.Text
        if #text > 0 then
            C2.debug("Text input: " .. text:sub(1, 50))
            C2.browser_send_text(text)
            textbox.Text = ""
        end
    end)

    C2.debug("browser_init done")
end

function C2.browser_shutdown()
    C2.restore_hidden_guis()
    if C2.browser then
        if C2.browser.screen_gui then
            pcall(function() C2.browser.screen_gui:Destroy() end)
        end
        C2.browser = nil
    end
end

function C2.browser_send_mouse(x, y, ev)
    C2.debug("Mouse send: " .. x .. "," .. y .. " ev=" .. ev)
    C2.send({type="mouse",x=x,y=y,event=ev})
end

function C2.browser_send_reset()
    C2.send({type="reset"})
end

function C2.browser_send_load(url)
    C2.send({type="load",url=url})
end

function C2.browser_send_key(ev_type, key)
    C2.debug("Key send: type=" .. ev_type .. " key=" .. key)
    C2.send({type="keyboard",event=ev_type,key=key})
end

function C2.browser_send_text(text)
    C2.debug("Text send: " .. text:sub(1,50))
    C2.send({type="text",text=text})
end

UserInputService.InputChanged:Connect(function(input, processed)
    if processed or not C2.browser or not C2.browser.ready then return end
    if input.UserInputType == Enum.UserInputType.MouseWheel then
        local x, y = C2.browser_coords()
        if x then
            C2.browser_send_mouse(x, y, input.Position.Z < 0 and 5 or 6)
        end
    end
end)

function C2.browser_handle(raw)
    local ok, err = pcall(function()
        if type(raw) == "buffer" then
            raw = buffer.tostring(raw)
        end

        local op = string.byte(raw, 1)
        C2.debug("browser_handle op=" .. op .. " len=" .. #raw)

        if op == 0 then
            local w, h = string.unpack("<I4I4", raw, 2)
            C2.debug("Resize: " .. w .. "x" .. h)
            C2.browser.width = w
            C2.browser.height = h

            local ok2, ei = pcall(AssetService.CreateEditableImage, AssetService, {
                Size = Vector2.new(w, h),
            })
            if ok2 and ei then
                if C2.browser.editable_image then
                    pcall(function() C2.browser.editable_image:Destroy() end)
                end
                C2.browser.editable_image = ei
                C2.browser.image_label.ImageContent = Content.fromObject(ei)
                C2.browser.viewport.UIAspectRatioConstraint.AspectRatio = w / h
                C2.browser.ready = true
                C2.debug("EditableImage created: " .. w .. "x" .. h)
            else
                C2.debug("CreateEditableImage failed: " .. tostring(ei))
            end

        elseif op == 1 and C2.browser.ready then
            local cx = string.byte(raw, 2)
            local cy = string.byte(raw, 3)
            local data_len = string.unpack("<I4", raw, 4)
            C2.debug("Chunk " .. cx .. "," .. cy .. " data_len=" .. data_len)

            local ox = cx * CHUNK_SIZE
            local oy = cy * CHUNK_SIZE
            local cw = math.min(CHUNK_SIZE, C2.browser.width - ox)
            local ch = math.min(CHUNK_SIZE, C2.browser.height - oy)

            local pixel_str = raw:sub(8, 7 + data_len)
            local pixel_buf = buffer.fromstring(pixel_str)
            C2.browser.editable_image:WritePixelsBuffer(
                Vector2.new(ox, oy),
                Vector2.new(cw, ch),
                pixel_buf
            )
        end
    end)
    if not ok then
        C2.debug("browser_handle error: " .. tostring(err))
    end
end

local function connect()
    local ok, result = pcall(WebSocket.connect, WS_URL)
    if not ok then
        task.wait(RECONNECT_DELAY)
        connect()
        return
    end
    ws = result
    C2.debug("WS CONNECTED to " .. WS_URL)
    ws.OnMessage:Connect(function(raw)
        if type(raw) == "buffer" then
            if not C2.browser then C2.browser_init() end
            if C2.browser and C2.browser.active then C2.browser_handle(raw) end
            return
        end
        if type(raw) ~= "string" then return end
        if raw == "ping" then return end

        local b = raw:byte(1)
        if b and b <= 1 then
            if not C2.browser then C2.browser_init() end
            if C2.browser and C2.browser.active then C2.browser_handle(raw) end
            return
        end

        if b == 123 then  -- "{"

            local ok, data = pcall(function() return game:GetService("HttpService"):JSONDecode(raw) end)
            if ok and type(data) == "table" and data.type then
                if data.type == "start_browser" then
                    C2.browser_init()
                    C2.hide_all_guis()
                elseif data.type == "stop_browser" then
                    C2.restore_hidden_guis()
                    C2.browser_shutdown()
                elseif data.type == "http_request" then
                    local req_fn = (syn and syn.request) or request
                    if not req_fn then return end
                    local req = {
                        Url = data.url or data.Url or "",
                        Method = data.method or data.Method or "GET",
                        Headers = data.headers or data.Headers or {},
                        Body = data.body or data.Body or "",
                    }
                    local ok, result = pcall(function()
                        local r = req_fn(req)
                        if type(r) == "table" and r.Success ~= nil and not r.StatusCode then
                            r.StatusCode = r.Success and 200 or 0
                        end
                        return r
                    end)
                    local resp = ok and result or {StatusCode = 0, Body = tostring(result), Headers = {}}
                    if type(resp.Body) == "buffer" then
                        resp.Body = buffer.tostring(resp.Body)
                    end
                    pcall(function()
                        ws:Send(game:GetService("HttpService"):JSONEncode({
                            type = "http_response",
                            id = data.id,
                            response = {
                                StatusCode = resp.StatusCode or 0,
                                Body = resp.Body or "",
                                Headers = resp.Headers or {},
                            }
                        }))
                    end)
                    return
                end
                if C2.on_message then
                    local ok2, err2 = pcall(C2.on_message, data)
                    if not ok2 then
                        warn("[C2] on_message error:", err2)
                        C2.send({type = "client_error", error = tostring(err2), raw_type = tostring(data.type)})
                    end
                end
                return
            end
        end

        C2.unload()
        C2.debug("loading module: " .. raw:sub(1, 80))
        local fn, err = loadstring(raw)
        if fn then
            C2.debug("module loaded, running...")
            local s, e = pcall(fn)
            if not s then
                warn("[C2]", e)
                C2.debug("module error: " .. tostring(e))
            else
                C2.debug("module ran OK")
            end
        else
            warn("[C2] loadstring:", err)
            C2.debug("loadstring error: " .. tostring(err))
        end
    end)
    ws.OnClose:Connect(function()
        C2.debug("WS CLOSED, reconnecting in " .. RECONNECT_DELAY .. "s")
        C2.browser_shutdown()
        ws = nil
        task.wait(RECONNECT_DELAY)
        C2.debug("WS reconnecting...")
        connect()
    end)
    C2.debug("sending hello")
    C2.send({
        type = "hello",
        userId = Players.LocalPlayer.UserId,
        placeId = game.PlaceId,
        playerName = Players.LocalPlayer.DisplayName
    })
    C2.debug("hello sent")
    task.spawn(function()
        while ws do
            task.wait(30)
            pcall(function() ws:Send("ping") end)
        end
    end)
end
connect()

-- Teleport persistence stub disabled for now (writefile triggers auto-exec in some executors, creating 2nd WS connection)
-- pcall(writefile, "c2_payload.txt", [[...]])
