-- Course materials only; no tutoring, chat interception, or gameplay changes.
local Http=game:GetService("HttpService")
local TextService=game:GetService("TextService")
local Config=require(script.Parent.MaterialsConfig)
local Store=game:GetService("DataStoreService"):GetDataStore("StudyMate_Materials_v1")
local M={preview=game:GetService("RunService"):IsStudio()}
if M.preview then
	local memory={}
	local function copy(v) return v and Http:JSONDecode(Http:JSONEncode(v)) end
	Store={GetAsync=function(_,k)return copy(memory[k]) end,UpdateAsync=function(_,k,fn)memory[k]=fn(copy(memory[k]));return copy(memory[k]) end}
end
local cache,external,busy,last={},{},{},{}
local function fail(s)error(s,0) end
local function clean(v,max,optional)
	if optional and (v==nil or v=="") then return "" end
	if type(v)~="string" or not utf8.len(v) or #v>max or not v:find("%S") then fail("Check required fields and length limits.") end
	return v:gsub("[\000-\008\011\012\014-\031]","")
end
local function fresh()return {version=1,courses={},documents={}} end
local function find(items,id)for _,v in ipairs(items)do if v.id==id then return v end end end
local function load(p)
	local ok,d=pcall(Store.GetAsync,Store,"u:"..p.UserId)
	if not ok then fail("Your materials could not be loaded. Please try again.") end
	d=d or fresh();if d.version~=1 then fail("Unsupported library version") end
	cache[p]=d;return d
end
local function update(p,fn)
	local ok,d=pcall(function()return Store:UpdateAsync("u:"..p.UserId,function(old)
		local data=old or fresh();if data.version~=1 then fail("Unsupported library version") end
		fn(data);data.selected=nil;data.activeCourse=nil
		if #Http:JSONEncode(data)>Config.MaxLibraryBytes then fail("Notes library is full") end
		return data
	end)end)
	if not ok then fail("Could not save. Check your limits or try again; existing notes were not overwritten.") end
	cache[p]=d;return d
end
local function filter(p,s)
	if not s or s=="" then return "" end
	local ok,v=pcall(function()return TextService:FilterStringAsync(s,p.UserId):GetNonChatStringForUserAsync(p.UserId)end)
	if not ok then fail("Text checking is unavailable. Please try again.") end
	return v
end
function M.configured()return (not M.preview or Config.AllowStudioBackend==true) and Config.BackendURL:match("^https://[^/]+$")~=nil end
local function backend(p,path,payload)
	if not M.configured() then fail("PDF uploads are not connected yet. Pasted notes are available.") end
	payload.userId=tostring(p.UserId)
	local ok,r=pcall(function()return Http:RequestAsync({Url=Config.BackendURL.."/v1/game/"..path,Method="POST",Headers={["Content-Type"]="application/json",["X-StudyMate-Key"]=Http:GetSecret(Config.SecretName),["X-Universe-Id"]=tostring(game.GameId)},Body=Http:JSONEncode(payload)})end)
	if not ok or type(r.Body)~="string" or #r.Body>180000 then fail("PDF service unavailable. Try again later.") end
	if not r.Success then
		local messages={
			[400]="Check the import code, title, and selected course.",
			[404]="PDF or import code not found. The code may have expired or already been used.",
			[409]="Your PDF library is full. Delete a PDF and try again.",
			[429]="Too many requests. Please wait and try again.",
		}
		fail(messages[r.StatusCode] or "PDF service unavailable. Try again later.")
	end
	local good,data=pcall(Http.JSONDecode,Http,r.Body)
	if not good or type(data)~="table" then fail("Invalid PDF service response") end
	return data
end
local function view(p,data,status)
	local out={courses={},documents={},preview=M.preview,pdfConfigured=M.configured(),status=status or (M.preview and "Saved for this Studio test session" or "Saved")}
	for _,c in ipairs(data.courses)do table.insert(out.courses,{id=c.id,title=filter(p,c.title),number=filter(p,c.number)})end
	local docs=table.clone(data.documents)
	for _,d in ipairs(external[p] or {})do if find(data.courses,d.courseId)then table.insert(docs,d)end end
	for _,d in ipairs(docs)do table.insert(out.documents,{id=d.id,courseId=d.courseId,lecture=filter(p,d.lecture),unit=filter(p,d.unit),chapter=filter(p,d.chapter),kind=d.kind,category=d.kind=="notes" and "notes" or (d.category=="exam" and "exam" or "lecture"),status=d.status or "ready"})end
	return out
end
local function dispatch(p,action,a)
	local data=action=="List" and load(p) or cache[p] or load(p)
	if action=="List" then
		local status
		if M.configured() then
			local ok,r=pcall(backend,p,"library",{courses=data.courses})
			if ok then external[p]=r.documents or {};status="PDFs refreshed" else external[p]={};status="PDF service unavailable; your notes are still here" end
		end
		return view(p,data,status)
	elseif action=="CreateCourse" then
		local c={id=Http:GenerateGUID(false),number=clean(a.number,32),title=clean(a.title,100)}
		data=update(p,function(d)if #d.courses>=Config.MaxCourses then fail("Course limit")end;table.insert(d.courses,c)end)
	elseif action=="SaveNotes" then
		local cid=clean(a.courseId,80)
		local id=a.id and clean(a.id,80) or "note-"..Http:GenerateGUID(false)
		local doc={id=id,courseId=cid,kind="notes",category="notes",lecture=clean(a.lecture,100),unit=clean(a.unit,80,true),chapter=clean(a.chapter,80,true),text=clean(a.text,Config.MaxNoteBytes)}
		data=update(p,function(d)
			if not find(d.courses,cid)then fail("Course not found")end
			local old=find(d.documents,id)
			if a.id and (not old or old.courseId~=cid or old.kind~="notes")then fail("Note not found")end
			if old then for k,v in pairs(doc)do old[k]=v end else
				if #d.documents>=Config.MaxDocuments then fail("Document limit")end;table.insert(d.documents,doc)
			end
		end)
	elseif action=="ReadNotes" then
		local d=find(data.documents,clean(a.id,80));if not d or d.kind~="notes" then fail("Note not found")end
		return {note={id=d.id,courseId=d.courseId,lecture=filter(p,d.lecture),unit=filter(p,d.unit),chapter=filter(p,d.chapter),text=filter(p,d.text)},status="Your saved notes"}
	elseif action=="ImportPDF" then
		local cid=clean(a.courseId,80)
		if not find(data.courses,cid) then fail("Choose a course first.") end
		local code=clean(a.code,40):upper():gsub("[%s%-]","")
		if #code~=32 or code:find("[^A-F0-9]") then fail("Paste the complete PDF import code.") end
		if a.category~="lecture" and a.category~="exam" then fail("Choose a PDF category.") end
		backend(p,"import",{courseId=cid,code=code,category=a.category,lecture=clean(a.lecture,100),unit=clean(a.unit,80,true),chapter=clean(a.chapter,80,true)})
		local synced,library=pcall(backend,p,"library",{})
		if synced then external[p]=library.documents or {} end
		return view(p,data,synced and "PDF imported into your course" or "PDF imported. Refresh to see it.")
	elseif action=="ReadPDF" then
		local id=clean(a.id,80)
		local doc=find(external[p] or {},id)
		if not doc or not find(data.courses,doc.courseId) then fail("Refresh PDFs and try again.") end
		local page=a.page or 1
		if type(page)~="number" or page%1~=0 or page<1 or page>100 then fail("Invalid text section.") end
		local r=backend(p,"read",{documentId=id,page=page})
		if type(r.text)~="string" or #r.text>8000 or type(r.pageCount)~="number" or r.pageCount<1 or r.pageCount>100 then fail("Invalid PDF text response.") end
		return {pdf={id=id,lecture=filter(p,r.lecture),text=filter(p,r.text),page=page,pageCount=r.pageCount},status="PDF text — section "..page.." of "..r.pageCount}
	elseif action=="DeleteDocument" then
		local id=clean(a.id,80);local d=find(data.documents,id)
		if not d then d=find(external[p] or {},id);if not d then fail("Document not found")end;backend(p,"delete",{documentId=id})end
		data=update(p,function(v)for i=#v.documents,1,-1 do if v.documents[i].id==id then table.remove(v.documents,i)end end end)
		for i=#(external[p] or {}),1,-1 do if external[p][i].id==id then table.remove(external[p],i)end end
	elseif action=="DeleteCourse" then
		local id=clean(a.id,80);if not find(data.courses,id)then fail("Course not found")end
		if M.configured()then backend(p,"delete-course",{courseId=id})end
		data=update(p,function(v)
			for i=#v.courses,1,-1 do if v.courses[i].id==id then table.remove(v.courses,i)end end
			for i=#v.documents,1,-1 do if v.documents[i].courseId==id then table.remove(v.documents,i)end end
		end)
	else fail("Unknown materials action")end
	return view(p,data)
end
function M.init()
	local remote=game.ReplicatedStorage.AIU.Remotes:FindFirstChild("StudyMaterials") or Instance.new("RemoteFunction")
	remote.Name="StudyMaterials";remote.Parent=game.ReplicatedStorage.AIU.Remotes
	remote.OnServerInvoke=function(p,action,a)
		if type(action)~="string" or type(a)~="table" then return {ok=false,error="Invalid request"}end
		if busy[p] or (last[p]and os.clock()-last[p]<.7)then return {ok=false,error="Please wait a moment."}end
		busy[p]=true;last[p]=os.clock();local ok,r=pcall(dispatch,p,action,a);busy[p]=nil
		return ok and {ok=true,data=r} or {ok=false,error=tostring(r):sub(1,220)}
	end
	game.Players.PlayerRemoving:Connect(function(p)cache[p]=nil;external[p]=nil;busy[p]=nil;last[p]=nil end)
end
return M

