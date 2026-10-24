local M={}
function M.init(options)
	local player=game.Players.LocalPlayer
	local UIS=game:GetService("UserInputService")
	local remote=game.ReplicatedStorage.AIU.Remotes:WaitForChild("StudyMaterials")
	local function make(class,props,parent)local o=Instance.new(class);for k,v in pairs(props)do o[k]=v end;o.Parent=parent;return o end
	local gui=make("ScreenGui",{Name="StudyMaterials",ResetOnSpawn=false,DisplayOrder=55},player.PlayerGui)
	local function button(text,parent,fn)
		local b=make("TextButton",{Text=text,Size=UDim2.new(1,-10,0,38),TextWrapped=true,BackgroundColor3=Color3.fromRGB(52,76,112),TextColor3=Color3.new(1,1,1),Font=Enum.Font.Gotham,TextSize=15},parent)
		make("UICorner",{CornerRadius=UDim.new(0,7)},b);b.Activated:Connect(fn);return b
	end
	local launcher=button("Study Materials",gui,function()end);launcher.Size=UDim2.fromOffset(160,38);launcher.Position=UDim2.new(1,-178,0,62)
	local panel=make("Frame",{Visible=false,AnchorPoint=Vector2.new(.5,.5),Position=UDim2.fromScale(.5,.5),Size=UDim2.fromScale(.9,.83),BackgroundColor3=Color3.fromRGB(23,30,48)},gui)
	make("UISizeConstraint",{MaxSize=Vector2.new(1050,800)},panel);make("UICorner",{CornerRadius=UDim.new(0,12)},panel)
	make("TextLabel",{Text="Study Materials",Position=UDim2.fromOffset(18,12),Size=UDim2.new(1,-90,0,30),BackgroundTransparency=1,TextColor3=Color3.new(1,1,1),Font=Enum.Font.GothamBold,TextSize=22,TextXAlignment=Enum.TextXAlignment.Left},panel)
	local close=button("X",panel,function()end);close.Size=UDim2.fromOffset(38,32);close.Position=UDim2.new(1,-50,0,10);close.Modal=true
	local tabs=make("Frame",{Position=UDim2.fromOffset(18,54),Size=UDim2.new(1,-36,0,42),BackgroundTransparency=1},panel)
	make("UIListLayout",{FillDirection=Enum.FillDirection.Horizontal,Padding=UDim.new(0,6)},tabs)
	local content=make("ScrollingFrame",{Position=UDim2.fromOffset(18,110),Size=UDim2.new(1,-36,1,-162),CanvasSize=UDim2.new(),AutomaticCanvasSize=Enum.AutomaticSize.Y,BackgroundTransparency=1,BorderSizePixel=0,ScrollBarThickness=6},panel)
	local layout=make("UIListLayout",{Padding=UDim.new(0,10),SortOrder=Enum.SortOrder.LayoutOrder},content)
	local status=make("TextLabel",{Text="",Position=UDim2.new(0,18,1,-44),Size=UDim2.new(1,-36,0,36),TextWrapped=true,BackgroundTransparency=1,TextColor3=Color3.fromRGB(170,209,237),TextSize=14,TextXAlignment=Enum.TextXAlignment.Left},panel)
	local data={courses={},documents={}};local course,editing,reading=nil,nil,nil;local tab="Courses";local busy=false;local render
	local function label(text)return make("TextLabel",{Text=text,Size=UDim2.new(1,-12,0,0),AutomaticSize=Enum.AutomaticSize.Y,TextWrapped=true,RichText=false,BackgroundTransparency=1,TextColor3=Color3.fromRGB(230,236,245),Font=Enum.Font.Gotham,TextSize=16,TextXAlignment=Enum.TextXAlignment.Left,TextYAlignment=Enum.TextYAlignment.Top},content)end
	local function field(placeholder,height,value)
		local b=make("TextBox",{Text=value or "",PlaceholderText=placeholder,Size=UDim2.new(1,-12,0,height or 42),MultiLine=(height or 42)>50,ClearTextOnFocus=false,TextWrapped=true,TextSize=16,Font=Enum.Font.Gotham,BackgroundColor3=Color3.fromRGB(36,46,66),TextColor3=Color3.new(1,1,1),PlaceholderColor3=Color3.fromRGB(160,174,195),TextXAlignment=Enum.TextXAlignment.Left,TextYAlignment=Enum.TextYAlignment.Top},content)
		make("UIPadding",{PaddingLeft=UDim.new(0,10),PaddingTop=UDim.new(0,10),PaddingRight=UDim.new(0,10)},b);return b
	end
	local function request(action,payload)
		if busy then return end;busy=true;status.Text="Working…"
		local ok,r=pcall(remote.InvokeServer,remote,action,payload or {});busy=false
		if not ok or not r or not r.ok then status.Text=ok and r and r.error or "Connection failed. Try again.";return end
		local v=r.data;status.Text=v.status or "Saved"
		if v.courses then
			data=v;local found=false;for _,c in ipairs(data.courses)do if c.id==course then found=true end end
			if not found then course=data.courses[1] and data.courses[1].id end
		end
		return v
	end
	local function perform(action,payload)if request(action,payload)then render()end end
	local function deletion(b,action,id)
		if b:GetAttribute("Confirm")then editing=nil;perform(action,{id=id})else b:SetAttribute("Confirm",true);b.Text="Confirm deletion"end
	end
	render=function()
		for _,c in ipairs(content:GetChildren())do if c~=layout then c:Destroy()end end;content.CanvasPosition=Vector2.zero
		if data.preview then label("Studio preview: notes saved here last only for this test session.")end
		if tab=="Courses"then
			label("Choose a course")
			for _,c in ipairs(data.courses)do button((course==c.id and "● " or "○ ")..c.number.." — "..c.title,content,function()course=c.id;editing=nil;tab="Paste Notes";render()end)end
			label("Add a course")
			local number=field("Course number — e.g. BIO 202");local title=field("Course title")
			button("Add course",content,function()perform("CreateCourse",{number=number.Text,title=title.Text})end)
			if course then local b;b=button("Delete selected course and its materials",content,function()deletion(b,"DeleteCourse",course)end)end
			return
		end
		local courseName="";for _,c in ipairs(data.courses)do if c.id==course then courseName=c.number.." — "..c.title end end
		if courseName==""then label("Add or select a course first.");button("Choose course",content,function()tab="Courses";render()end);return end
		button("Course: "..courseName.."  ·  Change",content,function()tab="Courses";render()end)
		if tab=="Paste Notes"then
			label(editing and "Edit saved notes" or "Paste your lecture notes")
			local name=field("Lecture / notes title",42,editing and editing.lecture)
			local unit=field("Unit (optional)",42,editing and editing.unit)
			local chapter=field("Chapter (optional)",42,editing and editing.chapter)
			local notes=field("Paste your notes here. New lines are preserved.",220,editing and editing.text)
			label("Up to 20,000 bytes per note. Add more notes for additional lectures.")
			button(editing and "Save changes" or "Save notes",content,function()
				if request("SaveNotes",{id=editing and editing.id,courseId=course,lecture=name.Text,unit=unit.Text,chapter=chapter.Text,text=notes.Text})then editing=nil;render()end
			end)
			if editing then button("Cancel editing",content,function()editing=nil;render()end)end
			label("Saved notes")
			for _,d in ipairs(data.documents)do if d.courseId==course and d.kind=="notes"then
				button(d.lecture.."  ·  Open / edit",content,function()local r=request("ReadNotes",{id=d.id});if r then editing=r.note;render()end end)
				local b;b=button("Delete "..d.lecture,content,function()deletion(b,"DeleteDocument",d.id)end)
			end end
		else
			local category=tab=="Practice Exams" and "exam" or "lecture"
			if reading then
				label(reading.lecture)
				label("Text section "..reading.page.." of "..reading.pageCount.." · PDF layout and images are not included")
				label(reading.text)
				local function page(n)
					local r=request("ReadPDF",{id=reading.id,page=n})
					if r then reading=r.pdf;render() end
				end
				if reading.page>1 then button("Previous section",content,function()page(reading.page-1)end)end
				if reading.page<reading.pageCount then button("Next section",content,function()page(reading.page+1)end)end
				button("Back to PDFs",content,function()reading=nil;render()end)
				return
			end
			label(tab=="Practice Exams" and "Your practice exam PDFs" or "Your lecture slide PDFs")
			if not data.pdfConfigured then
				label("PDF importing is unavailable in this session. Your saved PDFs and pasted notes remain accessible.")
			else
				label("Import PDF")
				label("Paste your private import code. Codes expire after 15 minutes or a service restart.")
				local code=field("PDF import code")
				local name=field("Lecture / practice exam title")
				local unit=field("Unit (optional)")
				local chapter=field("Chapter (optional)")
				button("Import PDF into this course",content,function()
					if request("ImportPDF",{courseId=course,category=category,code=code.Text,lecture=name.Text,unit=unit.Text,chapter=chapter.Text}) then render() end
				end)
				label("PDFs are private to your library. Selectable text is supported; images and scanned pages are not displayed.")
			end
			button("Refresh PDFs",content,function()perform("List",{})end)
			local count=0
			for _,d in ipairs(data.documents)do if d.courseId==course and d.category==category then
				count+=1;label(d.lecture.."  ·  "..d.status)
				button("Read PDF text",content,function()
					local r=request("ReadPDF",{id=d.id,page=1})
					if r then reading=r.pdf;render()end
				end)
				local b;b=button("Delete PDF",content,function()deletion(b,"DeleteDocument",d.id)end)
			end end
			if count==0 then label("No PDFs added yet.")end
		end
	end
	local function show(on)
		panel.Visible=on
		if options.isPlaying()then if on then options.controls:Disable()else options.controls:Enable()end end
		if on then UIS.MouseBehavior=Enum.MouseBehavior.Default;UIS.MouseIconEnabled=true end
	end
	for _,name in ipairs({"Courses","Lecture PDFs","Practice Exams","Paste Notes"})do local b=button(name,tabs,function()tab=name;editing=nil;reading=nil;render()end);b.Size=UDim2.new(.25,-5,1,0)end
	local function toggle()show(not panel.Visible);if panel.Visible and request("List",{})then render()end end
	launcher.Activated:Connect(toggle);close.Activated:Connect(function()show(false)end)
	UIS.InputBegan:Connect(function(input,processed)if not processed and not UIS:GetFocusedTextBox() and input.KeyCode==Enum.KeyCode.M then toggle()end end)
	render()
end
return M

