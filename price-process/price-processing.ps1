# Настройки
# Главная папка, где лежат папки с прайсами и правилами обработки
$OutputEncoding = [Console]::OutputEncoding #[System.Text.Encoding]::getencoding('windows-1251')

$rootPath = "\\none\ps\" 
$scriptLogLevel = 1
#$script:logfileName = ""
$script:logfileName=$rootPath + "log.txt"
#$doNotUseArchives = $true
#$processOnlySelectedFolder = "elmir"
#$doNotSummarize = $true
# путь к 7-zip
 Set-Alias zip "C:\Program Files\7-Zip\7z.exe"
#
#в конце команда запуска скрипта





#=================================  log functions ===================================

function Write-Visible {
   param($InputObject) 

   $a = New-Object PSObject -Property @{ Object=$InputObject } | 
       Out-String #| Out-Host 
   return $a
}
 function retEx()
 {
	$error[0] |out-string
	return
 }

 function rotateLog ($maxSize = 5MB)
 {
   if ([string]$script:logfileName -ne "") 
   {
     if (test-path $script:logfileName) 
     {
        if ((Get-Item $script:logfileName).Length -gt $maxSize) {
            $suffix = ".old"
            $renameTo = [System.IO.Path]::GetFileNameWithoutExtension($script:logfileName)+$suffix #$num+[System.IO.Path]::GetExtension($script:logfileName)
            move-item -force -path $script:logfileName -destination $renameTo
        }
     }
   } 
 }

 function log([System.String] $text, $logFile = $script:logfileName)
 {
   #if ([bool]$script:logDoNotUseDate -ne $true) {$text = "$(Get-Date -Format yyyy.MM.dd-HH:mm:ss) $text"} #i.e. by default show time in logs
   $text = "$(Get-Date -Format yyyy.MM.dd-HH:mm:ss) $text"
   if ([string]$logFile -eq "") 
   {
     write-host $text 
   } else {
     echo $text >> $logFile
     write-host $text 
   }
 }

 function logException{
    log "Logging current exception.";
    $s = retEx
    log $s
    $script:errorOccured = $true
    if ($script:errorsAt.length -gt 0) 
    {
        $name_present = $false
        foreach ($name in $script:errorsAt)
        { if ($name -eq $script:currentName) { $name_present = $true } }
        if (-not $name_present) { $script:errorsAt += $script:currentName }
    }
    else 
    { $script:errorsAt += $script:currentName }
        
 }

 function logDebug ([System.String] $text, $loglevel = 1) {
    if ($script:scriptLogLevel -ne $null) {
	if (($script:scriptLogLevel -ge $logLevel) -and ($script:scriptLogLevel -gt 0))
	{
		log ($text)
	}
    }
 }


#=================================  Excel functions ===================================
#
#
function xlApplyMacro ($macroFilename = "", $macroName, $destinationWorkbook = $script:wb, $macroSheetName = "Macrosheet", $fullFileName = "")
{

   if ($script:errorOccured) {log ("!!! Skip processing (error occured before): $macroName"); return} 
   try 
   {
     $wbName = $destinationWorkbook.name
     if  ([string]$macroFilename -eq "") 
     {
        $macroFilename = $script:path+$script:rulesSubDir+"xlMacro.xls"
        if ($fullFileName -ne "") { $macroFilename = $fullFileName }
        if (-not(test-path $macroFilename)) {throw "macro file '$macroFilename' not found"}
     }

     #check if $macrosheet exists
     $macroSheetExists = $false
     foreach ($dstWorksheet in $destinationWorkbook.Worksheets)
     {
        if ($dstWorksheet.name -eq $macroSheetName) { $macroSheetExists = $true; $macroSheetCodename = $dstWorksheet.codename }
     }
     #copy macrosheet if it does not exist
     if (-not $macroSheetExists)
     {
       $wb2Macro = xlOpenExcelFile -xlfullname $macroFilename
       $wb2Macro.Worksheets.Item($macroSheetName).copy($destinationWorkbook.Worksheets.item(1))
       logDebug "Sheet $macroSheetName copied from $macroFilename to $wbName"
       $macroSheetCodename = $destinationWorkbook.Worksheets.item(1).codename
       xlCloseExcelFile -workbook $wb2Macro
     }
     #apply macro
     logDebug "Macro $macroname starting"
     $script:xl.application.run("'$wbName'!$macroSheetCodename.$macroname")
     logDebug "Macro $macroname finished"
   } catch {
     log ("Error applying macro from $macroFilename")
     logException
     if ($wb2Macro -ne $null) {$wb2Macro.close()}
     xlDeleteSheet -workbook $destinationWorkbook -SheetName $macroSheetName
     return
   }


}


 function xlSaveSheetToCsv($workbook = $script:wb, $SheetName="", $newSheetName="", $filepath="") 
#if SheetName = "" then use active sheet. if SheetName = "*" then save all sheets.
#if $filename = "" then use active sheet name. if $filepath="" then use workbook path
 {
   if ($script:errorOccured) {log ("!!! Skip processing (error occured before): saving excell sheet"); return}
   try {
        switch ($SheetName)
	{
		"" 	{$sheetsToProcess = $workbook.ActiveSheet}
		"*" 	{$sheetsToProcess = $workbook.sheets}
		default {$sheetsToProcess = $workbook.sheets.item($SheetName)}
	}

     if ($filepath -eq "")
     {
	$filepath = $workbook.path
     }

	#get path
	$regxp = [regex]"(.*\\)(.*)"
	$match = $regxp.match( $workbook.path )
	$result = $match.groups[$match.groups.count - 1].captures[0].value 
	#$result = $script:wb.path | split-path 

      
     if ($sheetsToProcess -ne $null) {
      foreach ($sheet in $sheetsToProcess) {
         logDebug ("Sheet "+$Sheet.Name+" saving")
	     $sheet.select()
	     $SheetName = $sheet.Name

     	     if ($newSheetName -ne "")
	     {
	     	$SheetName = $newSheetName + $sheet.index
	     }

     	     $filename =  $result + "_"+ $SheetName
	     $filefullname = $filepath +"\"+ $filename
     
	     $workbook.SaveAs("$filefullname.csv.process", $script:xlCSV)
	     #logDebug ("$SheetName saved")

	     $script:csvList.add("$SheetName","$filefullname"+".csv.process")
      }
     } 
   }
   catch
   {
#     log ("Error saving sheet $ActiveSheetName from file $script:xlfullname to $script:outputfullname")
     log ("Error saving sheet from file $script:xlfullname to $script:outputfullname")
     logException
     #xlCloseExcelFile
     return
   }
 }

 function xlDeleteSheet($SheetName="", $workbook = $script:wb)
 {
   try {
     logDebug "Trying to delete sheet: $SheetName"

     if  ($SheetName -ne "") 
     {
	    $workbook.sheets.item($SheetName).select()
     } 
     
     $SheetName = $workbook.ActiveSheet.Name
     $workbook.ActiveSheet.delete()
     logDebug "Sheet $SheetName deleted"
   }
   catch
   {
     log ("Error removing sheet $SheetName")
     logException
     return
   }
 }

 
 function xlOpenExcelFile ($xlfullname, $corruptLoad = $false)
 {
   try {
     if ($script:xl -eq $null)
     {
       $xlPIDsOld = get-process -name excel -ErrorAction silentlycontinue | select-object -expandproperty id  #get excel processes list before new excel opened
	   $script:xl=New-Object -ComObject "Excel.Application"
       $xlPIDsNew = get-process -name excel -ErrorAction silentlycontinue | select-object -expandproperty id  #get excel processes with new excel opened. 
       $script:xlPID = $xlPIDsNew | where { $xlPIDsOld -notcontains $_}   # must return only one integer ( new PID )
       if ( ($script:xl -ne $null) -and ($script:xlPID -ne $null)) {logDebug "Excel started"} else {log ("Error starting Excel"); logException}
       if ($script:xlPID.gettype().name -ne "int32" ) {log ("Error starting Excel"); logException}   # if not integer than more than one excel started? => error
     }
   } catch {
     log ("Error opening Excel")
     logException
     return 
   }
   try {
     $workbook = $null
     if ( $corruptLoad )
     {$workbook= $script:xl.workbooks.open($script:xlfullname,$false,$false,5,"","",$true,2,"",$false,$false,$false,$false,$false,2) }
     #Filename As String, [UpdateLinks], [ReadOnly], [Format], [Password], [WriteResPassword], [IgnoreReadOnlyRecommended], [Origin], [Delimiter], [Editable], [Notify], [Converter], [AddToMru], [Local], [CorruptLoad]
     # [CorruptLoad] = 2 = xlExtractData
     else 
     {$workbook=$xl.Workbooks.Open($xlfullname)}
     $script:xl.DisplayAlerts = $false
     if ($workbook -ne $null) {logDebug "File opened: $xlfullname"} else {log ("Error opening file $xlfullname. But where is exception?"); logException}
     return $workbook
   } catch {
     log ("Error opening file $xlfullname")
     logException
     xlCloseExcelFile
     return $null
   }
 }


  function xlAppToDefaults ()
  {
   try 
   {
       $xlCalculationAutomatic = -4105
       if ($script:xl.workbooks.count -gt 0) {$script:xl.workbooks.count; $script:xl.Calculation = $xlCalculationAutomatic }
       $script:xl.DisplayAlerts = $True
       $script:xl.DisplayStatusBar = $True
       $script:xl.EnableAnimations = $False
       $script:xl.EnableEvents = $True
       $script:xl.ScreenUpdating = $True
       logdebug ("Excel defaults returned")
   } catch {
     log ("Can't return Excel App defaults")
     return
   }
    
  }


  function xlCloseExcelFile ($workbook = $script:wb)
  {
   try {
     if (($workbook -eq "") -or ($workbook -eq $null))
     {  
        foreach ($wb in $script:xl.workbooks)
        {
            $wbname = $wb.name
            $wb.Close($true)
            logDebug "Workbook $wbname closed"
        }
     }
     else
     {
        $wbname = $workbook.name
        $workbook.Close($true)
        logDebug "Workbook $wbname closed"
     }
     if ($script:xl.workbooks.count -eq 0)
     {
	     #set excel to defaults
         xlAppToDefaults
         $script:xl.Quit()
         $a = [System.Runtime.Interopservices.Marshal]::ReleaseComObject($script:xl)
     	 logDebug "No workbooks remaining. Excel closed."
         #stop-process -id $script:xlPID -Force -ErrorAction silentlycontinue
     }
   } catch {
     log ("Error closing file $xlfullname or application.")
     logException
     $script:xl=$null
     stop-process -id $script:xlPID -Force -ErrorAction silentlycontinue
     return
   }
  }


#=================================  CSV content Processing functions ===================================
#
#

  function fRemoveEmptyLinesAndSpaces ()
  {
	$regexp = '(\s*\r?\n)+'
	$script:contents = [regex]::replace($script:contents, $regexp, "`r`n", 	@('IgnoreCase', 'SingleLine')) #delete empty rows
	logDebug "[Regex] applied: [$regexp]"
	$regexp = '$\r?\n'
	$script:contents = [regex]::replace($script:contents, $regexp, "", 		@('IgnoreCase', 'SingleLine')) #delete last empty row
	logDebug "[Regex] applied: [$regexp]"

        #example  .*".*$\r?\n   select whole line with symbol " in multiline mode (then replace with "" to delete)
        #example  (\s*\r?\n)+   select spaces and end of lines, spaces and empty lines in singleline mode (then replace with "`r`n" to delete them)
        #example  $\r?\n   	select last empty line in singleline mode (then replace with "" to delete it)
#        return $script:contents
  }                                   

  function fRemoveLinesWithSpecialText ($specialText="")
  {
        $regexp = '.*'+$specialText+'".*$\r?\n'
	$script:contents = [regex]::replace($script:contents, $regexp, "", 	@('IgnoreCase', 'Multiline')) #delete empty rows
        #example  .*".*$\r?\n   select whole line with symbol " in multiline mode (then replace with "" to delete)
        #example  (\s*\r?\n)+   select spaces and end of lines, spaces and empty lines in singleline mode (then replace with "`r`n" to delete them)
        #example  $\r?\n   	select last empty line in singleline mode (then replace with "" to delete it)
	logDebug "[Regex] applied: [$regexp]"
        #return $script:contents
  }                                   

  function fRemoveLineIfColumnTypedAs ($columnToCheck, $columnType = 'empty', $delimiter = $script:delimiter ) 
  #default $columnType for EmptyColumn. ie remove line if column empty
  #default delimiter = ';'
  #column types: empty = ""
  #		 price = float number only, delimeter "." or ","
  #		 date  = xxxx-xx-xxxx  	  , delimeter "." or "-"
  {
        switch ($columnType)
	{
		#must not finish with ; or .
		"" 	{$regexTemplate = '\s*'}
		"empty"	{$regexTemplate = '\s*'}
		"price"	{$regexTemplate = '\d+(?:\.|,)?\d*'}
		"date"	{$regexTemplate = '\d{1,4}(?:\.|-)\d{1,2}(?:\.|-)\d{1,4}'}
		default {$regexTemplate = '\s*'}
	}

        $columnToCheck = $columnToCheck -1; # because of search for next semicolon
        #tmp = csv excel parse;?(?:(?:"((?:[^"]|"")*)")|([^;]*)) 
        $regexp = '^(?:[^'+$delimiter+'\r\n]*?'+$delimiter+'){' +$columnToCheck+ '}' + $regexTemplate + $delimiter + '.*$\r?\n?'
	#log ("^" + $regexp + "^")
        #example ^(?:[^;\r\n]*?;){5}\s*;.*$\r?\n  - select whole line, when column next after 5semicolon contains only space or empty.
	$script:contents = [regex]::replace($script:contents, $regexp, "", @('IgnoreCase', 'Multiline')) 
	logDebug "[Regex] applied: [$regexp]"
#        return $script:contents
  }


  function csvRemoveStartEndLines ($firstLinesToRemove=0, $lastLinesToRemove=0)
  {
	#remove start lines and end lines
	$strEnd = "`n"
	$substringFrom = 0
	$substringTo = $script:contents.length-1; #because strings starts from 0
	#increment search for end of line
	for ($i=1; $i -le $firstLinesToRemove; $i++) 	{$substringFrom = ($script:contents).indexOf($strEnd, $substringFrom);  $substringFrom++}
	for ($i=1; $i -le $lastLinesToRemove; $i++) 	{$substringTo = ($script:contents).lastindexOf($strEnd, $substringTo);  $substringTo--}
	if ($script:contents[$substringTo-1] -eq "`r") { $substringTo--; }
	$substringLength = $substringTo - $substringFrom
	$script:contents = ($script:contents).substring($substringFrom, $substringLength)
	logDebug "Lines removed from start: $firstLinesToRemove, from end: $lastLinesToRemove"
#        return $script:contents
  }


  function fCleanAndCheckHeader ( $header= "" , $checkHeaderForChanges = $true)
  #used to clean data before header line
  #$checkHeaderForChanges - check for header changes comparing to pre-definded header. used to know when file structure changes.
  #header should be set in rules file. e.g. $header="num;name;price" or using $headerBeginsWith
  #
  {
	$searchFor = ""
	$strEnd = "`n"
	if ($header -ne "") 	{$searchFor = $header}
#	if ($headerBeginsWith -ne "")  {$searchFor = $headerBeginsWith}
	if ($searchFor -eq "")  {return}
	$indexHeaderStart = ($script:contents).indexOf($searchFor)
        if ([int32]$indexHeaderStart -lt 0) { $s = $script:contents[0..1024] -join ""; throw "Specified header not found [$header] {`r`n$s`r`n}" }   #search for header ending 1kb after 1st symbol of header
	#if $indexHeaderStart
	$indexHeaderStringEnd = ($script:contents).indexOf($strEnd, $indexHeaderStart+1)
	if ($checkHeaderForChanges)
	{
		if ($header.length -eq 0) 
		{ log ('Error: $checkForChanges set to true, but no $header for check provided') }
		else
		{ 
		        $length = $indexHeaderStringEnd - $indexHeaderStart
			$str =  ($script:contents).substring($indexHeaderStart, $length).trim()
			if ($header.trim() -ne $str) { log "New header:[$str]"; log "Old header:[$header]"; throw "Exception. Header changed. "; } else {logDebug ("Header OK")}
		}                                                             
	}
	$script:contents = ($script:contents).substring($indexHeaderStart)
        logDebug ("File beginng trimmed till header")
  }

#================================ line processor ===========================

  function SetArrayLength ($array, [int]$length, $newItemValue = "")
  {
	if ($array.length -gt $length) 
	{ #cut last items
		if ($length -le 0) {$array = @()} #in case of empty array
		$array = $array[0..($length-1)] 
	} 
	else
	{ 
		while ($array.length -lt $length) { $array += $newItemValue }
	}
	return ,$array
  }

$categoryItemClass = new-object psobject -Property @{
	level = $null		
	position = $null		
	value = $null		
}   #$category=$categoryClass.psobject.copy()

  # lp = line processor
  # i need to determine category level to properly assign category to data-line. or only last found category will be assigned (not suitable)
  # category level types:
  #   1. positional (line starting with N symbols, divided by M symbols). Category name starts with number or word.
  #   2. by including upper category (for ex. PC -> RAM, PC -> HDD -> 2.5)
  #   3. numbers (1.2   1.2.1 ...)
  #   4. symbols ( a)  b)  c)    c)> i) ii) iii)  )


function lpCategoriesProcessLine {
    param
    (
        [Parameter(Mandatory=$true, Position=0)]
        $inputLine,
	[Parameter(Mandatory=$true)]
        $columnToCheck, 
	[Parameter(Mandatory=$false)]
#	[ValidateSet('Positional')] #others maybe later
        $categoryType="Positional",
	[Parameter(Mandatory=$false)]
        $columnType = 'price',
	[Parameter(Mandatory=$false)]
        $delimiter = $script:delimiter ,
	[Parameter(Mandatory=$false)]
        $categoryNameRegexp = '([а-яА-ЯёЁa-zA-Z0-9])'  #at least one match group required
    )
    Process
    {
       	$regexp = '.*\(.*\)' #at least one match group required
	$check = [regex]::match($categoryNameRegexp, $regexp) 
	if (-not $check.success)  { throw "lpCategoriesProcessLine: at least two match groups required in '$categoryNameRegexp'" }

	if ($columnToCheck -lt 1) {$columnToCheck = 0} #in case of errors. column must be > 0 
       	$columnToCheck = $columnToCheck -1; # because of search for next semicolon
        switch ($columnType)
	{
		#must not finish with ; or .
		"" 	{$regexTemplate = '\s*'}
		"empty"	{$regexTemplate = '\s*'}
		"price"	{$regexTemplate = '\d+(?:\.|,)?\d*'} #float or decimal
		"date"	{$regexTemplate = '\d{1,4}(?:\.|-)\d{1,2}(?:\.|-)\d{1,4}'}
		default {$regexTemplate = '\s*'}
	}

    $regexp = '^(?:[^'+$delimiter+'\r\n]*?'+$delimiter+'){' +$columnToCheck+ '}' + $regexTemplate + $delimiter + '.*$\r?\n?'
	$columnTypeMatchResult = [regex]::match($inputLine, $regexp) 
	if ($columnTypeMatchResult.success)  #if string contains column typed $columnType  
	{ 
		#join categories into one string
		$categoryText =""
		$categoryTextDelimiter =""
		$max = $script:categories.length
		for ($i = 0; $i -lt $max; $i++) 
		{ 
			$categoryText += $categoryTextDelimiter + $script:categories[$i].value 
		  	$categoryTextDelimiter =">"
		}
		#append line to category string
		logdebug -text "category text: [$categoryText]" -loglevel 2
		$line = $categoryText + $delimiter + $inputLine
	}
	else
	{

		logdebug -text "matched category line: '$inputline'" -loglevel 2
		#this is category line -> we should check it level and add to categories array
	        if ($categoryType -eq "positional")
		{
			$newCategory = $categoryItemClass.psobject.copy()
	                #$categoryNameRegexp = '(group1-prefix-trash)(group2-category-[а-яА-ЯёЁa-zA-Z0-9])'
			$categoryHasText = [regex]::match($inputLine, $categoryNameRegexp) #search for first place of letters/numbers
			if ($categoryHasText.success -and ($categoryHasText.groups.count -ge 3))  #groups: 1st(0) - all string, 2nd(1) - column beginning and spaces, 3rd(2) - category text
			{ 
				# search for max level that has position < current position. delete levels > current. add this new level.
				$categoryColumnPosition = $categoryHasText.groups[1].index
				$categoryTextPosition = $categoryHasText.groups[2].index
				$newCategory.position = $categoryTextPosition - $categoryColumnPosition
				$newCategory.value = $inputLine.substring($categoryTextPosition).trim().trim($delimiter)
				$levelDetermined = $false
				for ($i = $script:categories.getUpperBound(0);  $i -ge 0 ; $i--) 
				{ 
					if ($newCategory.position -gt $script:categories[$i].position) {$levelDetermined = $true; $i++; break} 
				}
				if ($i -lt 0) { $i = 0 } #getUpperBound(0) = -1 if array is empty at first step
				
				$newCategory.level = $i
				#cut old categories on same level
				$script:categories = SetArrayLength -array $script:categories -length $i
				$script:categories += $newCategory
				
				if ($script:scriptLogLevel -ge 1) { $a = write-output $script:categories; logdebug -text "categories: {$a}" -loglevel 2}
			}
			else 	{}	#line does not contain letters or numbers. skip this line
		}
		#this is category line (contains only category text). we do not need it.
		$line = ""  
	}
	return $line
     }
}


  function lineProcessor ( $sheetName = "", $leaveHeaderFirstLine = $true)
  #let we have a struct:
  #	header-line
  #	category-line-level1
  #	  category-line-level2
  #	    category-line-levelx-1
  #	      category-line-levelx = last category before text
  #	      text

  # on each step:
  #	header-line
  #	category-line-level1
  #	  category-line-level2
  #	    category-line-level(x-1)
  #	      text;category-line-levelx
  #		  ^^^^^^^^^^^^^^^^^^^^^^ 
  #               do for each text line

  # how1: 
  # 1. replace all text (lines with special criteria) with text-id, saving text by array-id in memory (?). thus we got a tree-like struct.
  #	 category = select lines where columnX is empty. text = other lines
  # 2. convert tree-like array2 of lines by id:  [1]= ;catx;catx-1;...  
  #				    		 [2]= ;catx;catx-1;...
  # 3. replace each text-id "'r'n" with line from array2

  # how2:  -<< ok
  # skip first line (header).
  # 1. collect category data to array adding or deleting items (levels).
  # 2. search for 'n (end of line). save each line, skipping category lines. add category data to line start ( not to end because we dont know 'r'n or 'n)

  #to script send - $line, from script get - $script:returnLine


  {
        logdebug ("Starting line processing <$sheetname>")
	$strEnd = "`n"
	$curPos = 0
	$newContents = ""
	$initializeLP=$true  #for classes init.
	$firstLine = $true
    $addToHeader="category;"
	$counter=0

   	$script:categories = @() #for lp categories function

    $rulesScriptText = readRulesScript -templateName $sheetName -rulesName "lprules" #read script file to variable or spend 10 sec on each dot source

	$len = $script:contents.length-1; #because strings starts from 0
	while ($curPos -lt $len)	  #explore each line
	{
		$counter++
	        #read each line
	        $lastPos = $curPos
		$curPos = ($script:contents).indexOf($strEnd, $curPos)
		$curPos++ #for next search
		#logDebug "line#:$counter c:$curPos l:$lastPos"
                $substringLength = $curPos - $lastPos
		$line = ($script:contents).substring($lastPos, $substringLength)
		if ($leaveHeaderFirstLine -and $firstLine) { $firstLine = $false; $newContents += $addToHeader+$line; continue }
		if ($script:scriptLogLevel -ge 2) { if ($counter % 1000 -eq 0) {log ("line: $counter")} }

		applyRulesScript -scriptToExecute $rulesScriptText -comment "lpscript" -loglevel 3

		if ($script:returnLine.trim() -eq "") { $script:returnLine = "" }
		$newContents += $script:returnLine
	}
	$script:contents = $newContents
  }

#=================================  CSV I/O functions ===================================
#
#

  function csvRead ($csvFile, $encoding = [System.Text.Encoding]::Default) 
  #read csv file to string
  {
        $contents = ""
	try {
    		$inputfile = New-Object System.IO.StreamReader ($csvFile, $encoding )
    		$contents = $inputfile.ReadToEnd()
                if ($contents.length -eq 0) {	throw "Error csvRead: file $csvFile is empty"	}
	        $inputfile.Close()
		logDebug ("csvRead success. file:$csvFile")
	   } catch {
	     log ("Error csvRead: file $csvFile")
	     logException
	   } finally {
	     $inputfile.Dispose()
	   }
	return $contents
  }

  function csvWrite ($csvFile, $encoding = [System.Text.Encoding]::UTF8, $append = $false) 
  #write datastring to csv file 
  {
	try {
    		$outputfile = New-Object System.IO.StreamWriter ($csvFile, $append, $encoding)  #[System.Text.Encoding]::Default   #[System.Text.Encoding]::ASCII
       		$outputfile.Write($script:contents)
		$outputfile.Close()
		logDebug ("csvWrite success. file:$csvFile")
	   } catch {
	     log ("Error csvWrite: file $csvFile")
	     logException
	   } finally {
	     $outputfile.Dispose()
	   }
  }

  function csvReformat ($csvFile, $delimiter = $script:delimiter )
  {
	try {
        log ("csvRefomat starting. file: $csvFile")
        if ($script:headerExpressions -eq $null) {log ("No header expressions. skipping reformat."); return} 
        $csvData = import-csv -Path $csvFile -delimiter $delimiter  | Select-Object $($script:headerExpressions)
        if ($csvData -eq $null) {log ("Empty file. skipping reformat."); return} 
        $csvData | Export-Csv -Path $csvFile -delimiter $delimiter -encoding Default -NoTypeInformation 
        log ("csvRefomat completed.")
    } catch {
        log ("Error csvReformat: file: $csvFile")
	    logException
    }
  }
  
  function csvProcess ($sheetName="*", $deleteSource = $true)
  {

    if ($script:errorOccured) {log ("!!! Skip processing csv (error occured before): $sheetName"); return}
    $sheetsToProcess=@()
	try 
    {
        switch -regex ($SheetName)
		{
			"(?:\s|\*)" 	{ foreach ($item in $script:csvList.GetEnumerator()) { $sheetsToProcess += $item.name } }
			default 	{ $sheetsToProcess += $sheetName }
		}
        if ($sheetsToProcess -ne $null)
        {
            foreach ($sheet in $sheetsToProcess)
            {
    			logDebug ("Processing [sheet]: [$sheet]")
                $script:headerExpressions = $null  # got from csvrules
                $script:contents = csvRead -csvFile $script:csvList[$sheet]
                $rulesScriptText = readRulesScript -templateName $sheet -rulesName "csvrules"
                applyRulesScript -scriptToExecute $rulesScriptText  -comment "csvscript for $sheet"
    	  		$tempfilename = $script:csvList[$sheet] + ".tmp" #add .tmp
                csvWrite -csvFile $tempfilename
                csvReformat -csvFile $tempfilename
                $regexp = '\.process$'
	            $destName = [regex]::replace($script:csvList[$sheet], $regexp, '', 	@('IgnoreCase', 'SingleLine')) #delete ending .process
                $destName = $destName + ".result"
                move-item -force -path $tempfilename -destination $destName  #rename to file without .tmp
                if ($deleteSource) { remove-item -force -path $script:csvList[$sheet] }
                logDebug ("Processing [sheet] completed: [$sheet] {$destName} ")
            }
        } 
	} catch {
	     log ("Error csvProcess: sheetName $sheetName")
	     logException
	}
  }


  function applyRulesScript ($scriptToExecute, $comment ="", $loglevel = 1)
  {
	#if file found then use script stored in it else do nothing
   	if ($script:errorOccured) {log ("!!! Skip processing (error occured before): $scriptToExecute"); return}
	logDebug -text ">> Rules <$comment> applying" -loglevel $loglevel
    invoke-expression $scriptToExecute
	logDebug -text "<< Rules <$comment> applying finished" -loglevel $loglevel
  }

  function readRulesScript ($templateName, $rulesName = "csvrules")
  {
    $name = $rulesName+"-"+$templateName
    $path = $script:path + $script:rulesSubDir +"\*"
	$ruleFiles =  dir $path -include ("$rulesName*.ps1")
	$fileNotFound = $true
	#search for file csvrules-<sheetName>.ps1. 
	#One rules file could be used for several sheets if named for example not csvrules-Sheet1.ps1 
	#								      but csvrules-Sheet.ps1 and even csvrules.ps1
	while (($name.length -gt 0) -and ($fileNotFound))
	{
	  logDebug -text $name -loglevel 2
      if ($ruleFiles -ne $null)
      {
	   foreach ($file in $ruleFiles) 
	   {
		if ($file.name -eq $name+".ps1") 
		  {$fileNotFound = $false; $scriptToExecute = $script:path+$script:rulesSubDir+$name+".ps1"; break;} 
	   }
      } 
	  $name=$name.substring(0,$name.length-1); 
	}
    
	try 
    {
        if (-not $fileNotFound)
        {
    	   $inputfile = New-Object System.IO.StreamReader ($scriptToExecute, [System.Text.Encoding]::Default )
    	   $scriptText = $inputfile.ReadToEnd()
           $inputfile.Close()
        } else {
            throw "Script file not found in $path"
        }
        
	} catch {
	     log ("Error readRulesScript. Path: [$path]. Rules: [$rulesName]. Template [$templateName]")
	     $inputfile = $null
	     logException
	}
	return $scriptText
  }


  function csvMakeResult () #get *.tmp together
  {
	try {
		$s = [regex]::match($script:path,"(.*\\)(.*)") 
		$resultFileName = $script:path + '\' + $s.groups[$s.groups.count - 1].captures[0].value + ".csv.out"
		$tempFiles = $script:path + '\' + "*.tmp"
		cmd /c copy /b $tempFiles $resultFileName | out-null
		logDebug ("Copied tempfiles to $resultFileName")
		remove-item $tempFiles -force
		logDebug ("Removed tmpfiles: $tempfiles")
	} catch {
	    log ("Error csvMakeResult")
	    logException
	}
  }


  function csvModifyAfterSQLiteExport ($filename)
  {
    try 
    {
	logDebug ("Processing [csvfile]: [$filename]")
	$script:contents = csvRead -csvFile $filename -encoding [System.Text.Encoding]::UTF8
        $script:contents = $script:contents.trim()
        $regexp = ';'
	$script:contents = [regex]::replace($script:contents, $regexp, ","   , @('IgnoreCase', 'SingleLine')) #replace ;
        #make each column in quotes and replace ~~ by ;
        $regexp = '(^"?)(.*?)("?$)'
        $script:contents = [regex]::replace($script:contents, $regexp, '"$2"', @('IgnoreCase', 'MultiLine') )
        $regexp = '("?~~"?)'
        $script:contents = [regex]::replace($script:contents, $regexp, '";"' , @('IgnoreCase', 'MultiLine') )
	#replace "." to "," in price column
        $regexp = '(^(".*?";){6}"\d*)(\.)(\d*";.*)'
        $script:contents = [regex]::replace($script:contents, $regexp, '$1,$4' , @('IgnoreCase', 'MultiLine') ) + "`r`n"
	logDebug "[Regex] applied: [$regexp]"
	$filename = "$filename.result"
	$encoding = [System.Text.Encoding]::Default
	csvWrite -csvFile $filename -encoding $encoding
	logDebug ("Processing [csvfile] completed: [$filename] ")
    } catch 
    {
	log ("Error csvModifyAfterSQLiteExport: fileName $filename")
	logException
    }
  }                                   


  function addBraces
  {
    param
    (  
    [Parameter(
        Position=0, 
        Mandatory=$true, 
        ValueFromPipeline=$true,
        ValueFromPipelineByPropertyName=$true)
    ]
    [Alias('InputString')]
    [String[]]$inputStr
    ) 

    process 
    {
        if ($inputStr -ne "") 
            { return "($inputStr) " }
        else
            { return "" }
    }
  }


#=================================================================================
# add .result files to one file $script:resultcsv

function priceIsOld ($dataline, $filename="") {

    $regexp = '^"(.*?)";.*' #at least one match group required
    $check = [regex]::match($dataline, $regexp) 
    if (-not $check.success) 
    { log "[$filename] Date expression not found: [$dataline]" ; return $true }
    else
    {
        try
        {
            $dateTextValue = $check.groups[1].value
            if ($dateTextValue.length -eq 19) { $dateTextValue = $dateTextValue.substring(0,10)+"-"+$dateTextValue.substring(11,8)} #dd.MM.yyyy-HH:mm:ss. sometimes different chars in the middle. replace to space.
            [ref]$priceDateRef = get-date
            $dateConvertOK = [datetime]::tryParseExact($dateTextValue, "yyyy.MM.dd-HH:mm:ss", $null, [System.Globalization.DateTimeStyles]::none,$priceDateRef )
        } catch {
            logdebug "[$filename] Wrong date format. Non-price file?  [string]: [$dataline]"
        }

            if (-not $dateConvertOK) 
            {
               logdebug ("[$filename] Wrong date format [$dateTextValue]. Non-price file?  [string]: [$dataline]")
               return $true
            }
            else
            {
                $priceDate = $priceDateRef.value
                $dateWhenPriceStillValid = [DateTime]::Now.Subtract([TimeSpan]::FromDays($script:maxDaysOldPrice))
                if ($priceDate -ge $dateWhenPriceStillValid) 
                {
                   #logdebug ("price date valid")
                   return $false
                }  
                else 
                {
                   $text = "[$filename] Price date is older $script:maxDaysOldPrice days: $dateTextValue"
		   logdebug ($text)
	           log -text $text -logFile $script:statusLogFileName
                   return $true
                }
            }
    }
}

function summarize ($header){

  log (" ==> summarize .results")
  $files = dir "$script:resultsdir\*.result" | sort LastWriteTime -Descending
  if ($files -ne $null)
  {
    if (test-path -path $script:resultcsv) {remove-item -force $script:resultcsv}
    $needToWriteHeader = $true
    foreach ($file in $files)
    {
        try 
        {
            log ($file.fullname)
            $script:currentName = "afterProcessing " + $file.name
            $reader = New-Object System.IO.StreamReader ($file.fullname, [System.Text.Encoding]::Default)
            $writer = New-Object System.IO.StreamWriter ($script:resultcsv, $true, [System.Text.Encoding]::Default)
            
            if ($needToWriteHeader) {$needToWriteHeader = $false; $writer.writeline($header)}
            
            $reader.ReadLine() > $null # Skip first line (header).
            $skipFile = $false
            if ($script:checkPriceDate)
            {
                $dataline1 = $reader.ReadLine() # get first data line to check price date
                if ( priceIsOld -dataline $dataline1 -filename $file.name ) 
		{
		   $skipFile = $true
		}
            }
            if (-not $skipFile)
            {
                $writer.writeLine($dataline1)
                $writer.write($reader.ReadToEnd())
                   #low-memory case
                    #while ($reader.Peek() -ge 0) {
                    #$writer.writeline($reader.ReadLine())
                    #}
            }
            $reader.Close()
            $writer.Close()
        }
        catch
        {
        	$fname = $file.fullname
            log ("Error summarize: fileName $fname")
	        logException
        }
    }
    log (" ==>result file: $script:resultcsv")

  }

}


#=======================================================================================


function rootScript {

	$script:xlCSV = 6
	$script:rulesSubDir='\rules\'
	$script:priceScriptPath = $rulesSubDir+"script.ps1"
    $script:maxArchives = 4
    $script:archivesDir = '\archives\'
    $script:delimiter = ";"
	$script:resultcsv = "all.csv"   #fullpath suffix here
	$script:resultsdir = "-result\" #fullpath suffix here
    $script:errorsAt = @()
    $script:statusLogfileName=$script:rootPath + "status.log"
    $script:checkPriceDate = $true
    $script:maxDaysOldPrice = 7
        
	#prepare variables
    $script:errorOccured = $false
	$script:xlfullname = ""
	$script:path = ""        #path without '\'
	$script:xl = $null
	$script:wb = $null
	$script:csvList = @{}
	$script:contents = ""
    $script:xlpid = $null

	$script:rootPath = $script:rootPath.trimend('\')+'\'
    $script:resultsdir =  $script:rootPath + $script:resultsdir
    $script:resultcsv =  $script:rootPath + $script:resultcsv
    
	rotateLog

	log ("== start root script ==")
	#$mainTimer = [Diagnostics.Stopwatch]::StartNew()
	#$mainTimer.Stop()                
	#log ($mainTimer.elapsed)
	log ("loglevel: $script:scriptLogLevel")

	#get only folder names (not files) from $rootPath that contains $mainScriptPath excluding folders started with minus
	$dirs = dir $script:rootPath |  where {$_.name[0] -ne '-'} |  where {$_.Attributes -like '*Directory*'} | where {Test-Path -path "$($_.fullname)$priceScriptPath"} | select-object name,fullname
    if ([boolean]$processOnlySelectedFolder) 
    {
        $dirs = dir $script:rootPath $processOnlySelectedFolder  |  where {$_.Attributes -like '*Directory*'} | where {Test-Path -path "$($_.fullname)$priceScriptPath"} | select-object name,fullname
    }
	#decompress archives
    if ($dirs -eq $null) {$dirs = @()} #for foreach loops. ($null in powershell v2)
	foreach ($currentDir in $dirs)
	{
        $currentDir = $currentDir.fullname
		$archiveFiles = dir "$currentDir\*" -include ('*.rar', '*.zip', '*.7z') | sort LastWriteTime #-descending #without -recurse or \* include does not work
		if ($archivefiles -ne $null) 
		{
			foreach ($archivefile in $archivefiles)  
			{  
                $archivefilename = $archivefile.fullname
   				log ('Extracting ' +  $archivefile)
   				$stdoutput = zip x $archivefilename -aou "-o$currentDir" #-aou = aUto rename extracting file (for example, name.txt will be renamed to name_1.txt). -o$Dir - extract to $Dir
				if ($LASTEXITCODE -ne 0) { log ($stdoutput) }
			}
		}
	}
	#run scripts
	foreach ($currentDir in $dirs)
	{
        $script:currentName = $currentDir.Name
        $currentDir = $currentDir.fullname
		$scriptFileName = $currentDir+$priceScriptPath
		log ("== start script $scriptFileName ==")
		$script:path = $currentDir        #path without '\'

		$rulesScriptText = readRulesScript -templateName "" -rulesName "script"
		applyRulesScript -scriptToExecute $rulesScriptText  -comment ""
        #1. collect files. Move .result to results dir
        move-item -force -path $($script:path + "\*.result") -destination $script:resultsdir  

		#move sources to archives dir.
		$to = $currentDir + $archivesDir + "$(Get-Date -Format yyyyMMdd-HHmmss)"+'\'
		$alreadyProcessed = dir "$currentDir\*" -include ('*.rar', '*.zip', '*.7z', '*.xls*', '*.csv') 
        if ( ( $alreadyProcessed -ne $null ) -and ( -not ( [boolean]$script:doNotUseArchives ) ) -and ( -not $script:errorOccured ) )
        { 
            if(!(Test-Path $to))
		    {
                New-Item -Path $to -ItemType Directory -Force | Out-Null
		    }
            $alreadyProcessed | move-item -Destination $to -force 
        }
        #clean archives dir (only $script:maxArchives last)
        if ( (Test-Path "$currentDir$script:archivesDir") )
        {
		  $archivesToClean = dir "$currentDir$script:archivesDir" | where {$_.Attributes -like '*Directory*'} | sort lastWriteTime -Descending | select-object fullname
		  for ($i = $archivesToClean.length-1; $i -ge $script:maxArchives; $i--) 
          {
            $arhName=$archivesToClean[$i].fullname 
            log ("$arhName archived")
            Remove-item -recurse -force $arhName
          }
        }

		#clean variables
        #try close excel first
        try 
        { 
            if ($script:xl -ne $null) 
            {   
                if ($script:wb -ne $null) {$script:wb.close()}   
            } 
        } catch {}
        try 
        { 
            if ($script:xl -ne $null) 
            {   
                $script:xl.Quit()
            } 
        } catch {}
        #Remove-Variable -Scope script -name xlfullname
        #Remove-Variable -Scope script -name xl
        #Remove-Variable -Scope script -name wb
        #Remove-Variable -Scope script -name csvList
        #Remove-Variable -Scope script -name contents
        #Remove-Variable -Scope script -name doNotUseArchives
        #Remove-Variable -Scope script -name processOnlySelectedFolder
		$script:xlfullname = ""
		$script:xl = $null
		$script:wb = $null
		$script:csvList = @{}
		$script:contents = ""
        $script:doNotUseArchives = $false
        $script:processOnlySelectedFolder = ""
        if ($script:errorOccured) { log ("!!! SCRIPT PROCESSED WITH ERRORS !!!") }
        $script:errorOccured = $false
        
		log ("== end script $scriptFileName ==")
		log ("")
	}
    $script:currentName = "afterProcessing"
        
    if ( -not ( [boolean]$script:doNotSummarize ) ) 
    {
       summarize -header '"pricedate";"supplier";"supplierItemID";"category";"vendor";"partNumber";"name";"priceRUR";"priceUSD";"priceOther";"stock";"transit";"other"'     
    }
    $script:doNotSummarize = $false


if ($script:errorsAt.length -gt 0) 
{ 
    $errStr =  "== Errors found at scripts: " + $($script:errorsAt -join ", ");  
    log ($errStr);  
    log -text $errStr -logFile $script:statusLogFileName
}
log "== end root script =="
}

#======================================= main =============================================================================

rootScript
