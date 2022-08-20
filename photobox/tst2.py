import cv2
import fileinput
import os
import numpy as np
from matplotlib import pyplot as plt
import PySimpleGUI as sg
import PIL.Image, PIL.ImageTk, PIL.ImageGrab
import time
import win32gui, win32ui, win32con
import subprocess
from shutil import copyfile

def ResizeWithAspectRatio(imageshape, w_max=1000, h_max=1250):
    dim = None
    (h_image, w_image) = imageshape[:2]

    if w_image < w_max and h_image< h_max :
        #smaller -> enlarge
        if w_image/w_max > h_image/h_max :
                h_new = int( w_max * h_image / w_image )
                w_new = w_max
                aspect = w_image / w_max
        else:
                w_new = int( h_max * w_image / h_image )
                h_new = h_max
                aspect = h_image / h_max
        #     w_new = int( h_max * w_image / h_image )
        #     h_new = h_max
        #     aspect = h_image / h_max
        # else:
        #     h_new = int( w_max * h_image / w_image )
        #     w_new = w_max
        #     aspect = w_image / w_max
        print ("" + str(w_image) + "x" + str(h_image) +" -> " + str(w_new) + "x" + str(h_new) )
        return (w_new, h_new, aspect)

    #something bigger -> make small
    if w_image/w_max > h_image/h_max :
            h_new = int( w_max * h_image / w_image )
            w_new = w_max
            aspect = w_image / w_max
    else:
            w_new = int( h_max * w_image / h_image )
            h_new = h_max
            aspect = h_image / h_max
    print ("" + str(w_image) + "x" + str(h_image) +" -> " + str(w_new) + "x" + str(h_new) )
    return (w_new, h_new, aspect)

def do_nothing(x) :
    pass

def apply_clahe (img, cliplim, tilesize):
    lab= cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    #-----Splitting the LAB image to different channels-------------------------
    l, a, b = cv2.split(lab)
    #-----Applying CLAHE to L-channel-------------------------------------------
    clahe = cv2.createCLAHE(clipLimit=cliplim, tileGridSize=(tilesize,tilesize))
    cl = clahe.apply(l)
    #-----Merge the CLAHE enhanced L-channel with the a and b channel-----------
    limg = cv2.merge((cl,a,b))
    #-----Converting image from LAB Color model to RGB model--------------------
    final = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
    return final

def filterOutSaltPepperNoise(edgeImg):
    # Get rid of salt & pepper noise.
    count = 0
    lastMedian = edgeImg
    median = cv2.medianBlur(edgeImg, 3)
    while not np.array_equal(lastMedian, median):
        # get those pixels that gets zeroed out
        zeroed = np.invert(np.logical_and(median, edgeImg))
        edgeImg[zeroed] = 0

        count = count + 1
        if count > 70:
            break
        lastMedian = median
        median = cv2.medianBlur(edgeImg, 3)
    return median    

def findSignificantContour (img2):
            contours, hierarchy = cv2.findContours(
                img2,
                cv2.RETR_TREE,
                cv2.CHAIN_APPROX_SIMPLE
            )            
            # Find level 1 contours
            level1Meta = []
            for contourIndex, tupl in enumerate(hierarchy[0]):
                # Each array is in format (Next, Prev, First child, Parent)
                # Filter the ones without parent
                if tupl[3] == -1:
                    tupl = np.insert(tupl.copy(), 0, [contourIndex])
                    level1Meta.append(tupl)
            # From among them, find the contours with large surface area.
            contoursWithArea = []
            for tupl in level1Meta:
                contourIndex = tupl[0]
                contour = contours[contourIndex]
                area = cv2.contourArea(contour)
                contoursWithArea.append([contour, area, contourIndex])
           
            contoursWithArea.sort(key=lambda meta: meta[1], reverse=True)
            largestContour = contoursWithArea[0][0]
            return largestContour

def grab_screen(element, w, h, title):

    margin_title = 27
    margin_left = 13
    widget = element.Widget
    box = (widget.winfo_x(), widget.winfo_y(), widget.winfo_x() + w, widget.winfo_y() + h)
    left = 0 + margin_left + widget.winfo_x()
    top = 0 + margin_title + widget.winfo_y()
    w,h = w+1,h+1
    right = left + w
    bottom = top + h
    box = (left, top, right, bottom)

    fceuxHWND = win32gui.FindWindow(None, title)
#    rect = win32gui.GetWindowRect(fceuxHWND)
#    rect_cropped = (winfo_x(), rect[1], rect[2]-C, rect[3]-C)
#    frame = np.array(ImageGrab.grab(bbox=rect_cropped), dtype=np.uint8)
#    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    hwin = win32gui.GetDesktopWindow()
    #hwindc = win32gui.GetWindowDC(hwin)
    hwindc = win32gui.GetWindowDC(fceuxHWND)

    srcdc = win32ui.CreateDCFromHandle(hwindc)
    memdc = srcdc.CreateCompatibleDC()
    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(srcdc, w, h)
    memdc.SelectObject(bmp)
    memdc.BitBlt((0, 0), (w, h), srcdc, (left, top), win32con.SRCCOPY)
    
    signedIntsArray = bmp.GetBitmapBits(True)
    img = np.fromstring(signedIntsArray, dtype='uint8')
    img.shape = (h,w,4)

    srcdc.DeleteDC()
    memdc.DeleteDC()
    win32gui.ReleaseDC(hwin, hwindc)
    win32gui.DeleteObject(bmp.GetHandle())

    return cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)       



def gammaCorrection(img,gamma):
    ## [changing-contrast-brightness-gamma-correction]
    lookUpTable = np.empty((1,256), np.uint8)
    for i in range(256):
        lookUpTable[0,i] = np.clip(pow(i / 255.0, gamma/100) * 255.0, 0, 255)

    res = cv2.LUT(img, lookUpTable)
    ## [changing-contrast-brightness-gamma-correction]

    img_gamma_corrected = cv2.hconcat([img, res])
    return img_gamma_corrected

def alpha_beta_bymean (img, dest_mean, maxcounter = 60, alpha_src = 100, beta_src = 100, alpha_mult = 1, beta_mult = 1 ):
    roimean = cv2.mean(img)[0]
    print ("mean: ", roimean)
    counter = 0
    roimean = 0
    found = False
    while counter < maxcounter:
        counter +=  1
        alpha2 = ( alpha_src + counter*alpha_mult - 1 ) / 100
        beta2 = ( beta_src + counter*beta_mult - 100 )
        roi2 = cv2.convertScaleAbs(img, alpha=alpha2, beta=beta2)
        roimean = cv2.mean(roi2)[0]
        if roimean >= dest_mean:
            #bright + contrast found - ok
            #change frame 
            print ("mean new: ", roimean)
            print ("counter,alpha,beta: ", counter, alpha2, beta2)
            found = True
            break
    else :
        #counter ended
        #do not change frame
        print ("not found, last try mean,alpha,beta : ", roimean, alpha2, beta2 )
        #cv2.imshow('boot', roi2)
        #cv2.waitKey( 0 )
    return found, alpha2, beta2

def apply_part1 (img, drawing_setting, graph, mainImageID, threshold_only, forest_only, a_bar, b_bar, no_show = False):
    if drawing_setting['-THRESH RADIUS-'] % 2 == 0: 
        thresh_radius = drawing_setting['-THRESH RADIUS-'] + 1
    else :
        thresh_radius = drawing_setting['-THRESH RADIUS-'] 
    if drawing_setting['-SHOW SPEED-'] == 0: 
        show_speed = 1
    else:
        show_speed = int (drawing_setting['-SHOW SPEED-'])

    frame = img
    # frame = np.copy(img)
    hsrc, wsrc, chsrc = img.shape
    (w,h) = graph.CanvasSize 
    w,h = w-1,h-1
    (w, h, aspect) = ResizeWithAspectRatio (frame.shape, w,h)

    #preview
    if not (no_show):
        cv2.imshow('boot', cv2.resize(img, (w,h) ))
        cv2.waitKey( show_speed )

    #lightness correct via saturation HLS
    #  
    # lightness = int(drawing_setting['-HCL L-'])
    # if firstrun :  #calc auto lightness 
    #     #center of right side 100*50, assume no object
    #     y1,y2 = int(hsrc/2)-50, int(hsrc/2)+50
    #     x1,x2 = wsrc-50,wsrc
    #     roi = img[y1:y2,x1:x2]
    #     roimean = cv2.mean(roi)
    #     cv2.imshow('boot', roi)
    #     cv2.waitKey( 2000 )
    #     roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HLS)
    #     lumi_mean = cv2.mean(roi)[1]
    #     print ("mean, lumi mean: ", roimean, lumi_mean)
    #     diff = int(225 - lumi_mean) #225 = lumi ok
    #     if diff > 0 : 
    #         lightness = diff
    #     else :
    #         lightness = 0
    #     light_bar.update(lightness)

    # if last_lightness == None:
    #     last_lightness = lightness
    # if drawing_setting['-LIGHT-'] :
    #     resized = cv2.resize(frame, (w, h) )
    #     # cv2.imshow('boot', resized)
    #     # cv2.waitKey( 1000 )
    #     frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HLS)
    #     frame[:, :, 1] += lightness   #:, :, 1 - Lchannel
    #     frame = cv2.cvtColor(frame, cv2.COLOR_HLS2BGR)
    #     resized = cv2.resize(frame, (w, h) )
    #     cv2.namedWindow('boot', cv2.WINDOW_NORMAL)
    #     cv2.imshow('boot', resized)
    #     cv2.waitKey( 1000 )
    # if drawing_setting['-GAMMA-'] :
    #     resized = cv2.resize(frame, (w, h) )
    #     resized = gammaCorrection (resized, drawing_setting['-GAMMA VALUE-'])
    #     cv2.namedWindow('boot', cv2.WINDOW_NORMAL)
    #     cv2.imshow('boot', resized)
    #     cv2.waitKey( 1000 )

    alpha = drawing_setting['-ALPHA-'] / 100
    beta = drawing_setting['-BETA-'] - 100
    auto_detect = drawing_setting['-AUTOBRIGHTNESS-']

    if auto_detect : 
        #auto detect alpha, beta
        y1,y2 = int(hsrc/2)-50, int(hsrc/2)+50
        x1,x2 = wsrc-50,wsrc
        roi = img[y1:y2,x1:x2]
        result, alpha, beta = alpha_beta_bymean (roi, 225, maxcounter = 40, alpha_src = 100, beta_src = 100, alpha_mult=7 )
        if result:
            a_bar.update(alpha * 100)
            b_bar.update(beta + 100)
            drawing_setting['-ALPHA-'] = alpha * 100
            drawing_setting['-BETA-'] = beta + 100
            frame = cv2.convertScaleAbs(frame, alpha=alpha, beta=beta)
        else : #second try, brightness + 30
            print ('alpha not found, second try..')
            result, alpha, beta = alpha_beta_bymean (roi, 225, maxcounter = 40, alpha_src = 150, beta_src = 100, alpha_mult=7 )
            if result:
                a_bar.update(alpha * 100)
                b_bar.update(beta + 100)
                drawing_setting['-ALPHA-'] = alpha * 100
                drawing_setting['-BETA-'] = beta + 100
                frame = cv2.convertScaleAbs(frame, alpha=alpha, beta=beta)
    else:
        frame = cv2.convertScaleAbs(frame, alpha=alpha, beta=beta)            
        y1,y2 = int(hsrc/2)-50, int(hsrc/2)+50
        x1,x2 = wsrc-50,wsrc
        roi = frame[y1:y2,x1:x2]
        roimean = cv2.mean(roi)
        print ("mean curr: ", roimean)

    if drawing_setting['-CLAHE-'] :
        cliplim = int(drawing_setting['-CLAHE1-'])
        tilesize = int(drawing_setting['-CLAHE2-'])
        frame = apply_clahe (frame, cliplim, tilesize)
        if not (no_show):
            cv2.imshow('boot', cv2.resize(frame,(w,h)))
            cv2.waitKey( show_speed )

    readymask = None
    if threshold_only: #for dark on gray
        


        #color regions should be more dark for threshold
        #check left or right col for min max of gray
        roil = frame[0:hsrc,0]
        roir = frame[0:hsrc,wsrc-1]
        meanL, stddevL = cv2.meanStdDev(roil)
        meanR, stddevR = cv2.meanStdDev(roir)
        if stddevL < stddevR :
            minVal = np.min(roil)
            maxVal = np.max(roil)
            diffcol = roil[:,0] #r~g~b
            # if maxVal - minVal > 100 :
            #     diffcol_black = np.zeros((hsrc,1),np.uint8)
            #     for i in np.arange(0, int(hsrc/2), 100, np.uint16) :
            #         diff_col = diffcol_black
            #         diff_col[0+i:hsrc-i,0] = frame[0+i:hsrc-i,0]  
            #         minVal = np.min(diff_col)
            #         maxVal = np.max(diff_col)
            #         if maxVal - minVal < 100 : 
            #             break #exclude not gray on edges
            #         else :
            #             diff_col = diffcol_black
            #             minVal,maxVal = 150,220

        else:
            minVal = np.min(roir)
            maxVal = np.max(roir)
            diffcol = roir[:,0]
            # if maxVal - minVal > 100 :
                # diffcol_black = np.zeros((hsrc,1),np.uint8)
                # for i in np.arange(0, int(hsrc/2), 100, np.uint16) :
                #     diff_col = diffcol_black
                #     diff_col[0+i:hsrc-i,0] = frame[0+i:hsrc-i,0]  
                #     minVal = np.min(diff_col)
                #     maxVal = np.max(diff_col)
                #     if maxVal - minVal < 100 : 
                #         break #exclude not gray on edges
                #     else :
                #         diff_col = diffcol_black
                #         minVal,maxVal = 150,220
        # if maxVal - minVal > 100 :
        #     minVal = maxVal - 90

        minVal = minVal - 10
        if maxVal < 240 :
            maxVal = maxVal + 15


        if drawing_setting['-BLUR-'] :
            bl = int(drawing_setting['-BLUR VALUE-'])
            frame = cv2.GaussianBlur(frame, (bl, bl), 0)
        if drawing_setting['-BILATERAL-'] :
            frame = cv2.bilateralFilter(frame,-1,drawing_setting['-BILATERAL COLOR-'],drawing_setting['-BILATERAL SPACE-'])
        framegray = cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
        if drawing_setting['-THRESH-'] :
            if drawing_setting['-ADAPTIVE GAUSS-'] :
                thresh_mask = cv2.adaptiveThreshold( framegray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 
                                                int(thresh_radius), drawing_setting['-THRESH CONST-'])
                frame[thresh_mask == 255 ] = (255,255,255)
                if not (no_show):
                    cv2.imshow('boot', cv2.resize(thresh_mask,(w,h)))
                    cv2.waitKey( int(show_speed/2 + 1) )
                    cv2.imshow('boot', cv2.resize(frame,(w,h)))
                    cv2.waitKey( int(show_speed/2 + 1) )
                del framegray; del thresh_mask
            elif drawing_setting['-ADAPTIVE MEAN-'] :
                thresh_mask = cv2.adaptiveThreshold( framegray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 
                                                int(thresh_radius), drawing_setting['-THRESH CONST-'])
                frame[thresh_mask == 255 ] = (255,255,255)
                if not (no_show):
                    cv2.imshow('boot', cv2.resize(thresh_mask,(w,h)))
                    cv2.waitKey( int(show_speed/2 + 1) )
                    cv2.imshow('boot', cv2.resize(frame,(w,h)))
                    cv2.waitKey( int(show_speed/2 + 1) )
                del framegray; del thresh_mask
            elif drawing_setting['-SIMPLE-'] :
                _,thresh_mask = cv2.threshold( framegray, drawing_setting['-THRESH SIMPLE-'], 255, cv2.THRESH_BINARY)
                frame[thresh_mask == 255 ] = (255,255,255)
                if not (no_show):
                    cv2.imshow('boot', cv2.resize(thresh_mask,(w,h)))
                    cv2.waitKey( int(show_speed/2 + 1) )
                    cv2.imshow('boot', cv2.resize(frame,(w,h)))
                    cv2.waitKey( int(show_speed/2 + 1) )
                del framegray; del thresh_mask



        #regions where values out of min and max are regions of object, others needs to be checked:
        #gray  ~ r=g=b => r-g ~ 0, r-b ~ 0   rg+rg ~ 0 + mini_const. if sum > mini_const => object (colored region, not gray)
        #RGBmean = (RGB16+R+G+B) 
        #RGBmean = (RGBmean /3) 
        
        add = frame
        #diff from col
        RGB16 = np.zeros ((hsrc,wsrc), np.int16)
        diff_from_orig = RGB16
        add_diff = frame
        diffconst = drawing_setting['-GRAY DIFF-']
        diffstd = drawing_setting['-GRAY STD-']
        RGBmean = np.mean( add, axis = 2) #three color values to one gray
        RGBstd = np.std( add, axis = 2) #three color values to one gray
        if diffconst > 0: #select non object gray
            RGBdiff = ( RGBmean.transpose() - diffcol).transpose() #if small -> gray = gray of diffcol
            RGBdiff = np.where(RGBdiff>0 , RGBdiff, -1*RGBdiff)
            coeff_for_upper = drawing_setting['-GRAY TOPGRADIENT-']
            RGBdiff[0:int(hsrc/2),0:wsrc] /= coeff_for_upper #upper part more diff from 1st col
            coef_lighten = drawing_setting['-GRAY GRADIENT-'] #gradient lighten center
            lighten_center = np.linspace(1, coef_lighten, num = int(wsrc/2))
            RGBdiff[0:hsrc,0:int(wsrc/2)] *= lighten_center #left simple lighten
            lighten_center = np.linspace(coef_lighten, 1, num = wsrc-int(wsrc/2))
            RGBdiff[0:hsrc,int(wsrc/2):wsrc] *= lighten_center #right simple lighten
            
            add_diff[(RGBdiff < diffconst) ]=255
            if diffstd > 0 :
                add_diff[(RGBstd > diffstd) ]=0
            cv2.imshow('boot', cv2.resize(add,(w,h)) )
            cv2.waitKey( show_speed )
            #diff_from_orig_rgb = add - frame
            #diff_from_orig = cv2.cvtColor(diff_from_orig_rgb,cv2.COLOR_BGR2GRAY)
            diff_from_orig[(RGBdiff < diffconst) ]=255  #100% background
            #maxVal = maxVal - drawing_setting['-THRESH CONST-']
            #_,diffconstmask = cv2.threshold( add, 1, 255, cv2.THRESH_BINARY)

        add_diff = cv2.cvtColor(add,cv2.COLOR_BGR2GRAY)
        if drawing_setting['-GRAY CONST-'] == 0:
            add = add_diff
        else:

            if drawing_setting['-GRAY MANUAL-']:
                minVal = drawing_setting['-GRAY MIN-']
                maxVal = drawing_setting['-GRAY MAX-']
                if minVal > maxVal :
                    tmpV = maxVal
                    maxVal = minVal
                    minVal = tmpV
                elif minVal == maxVal :
                    maxVal += 1

            #RGBmean = np.mean( frame, axis = 2)
            R, G, B = cv2.split(frame)
            rg = RGB16+R-G
            # cv2.imshow('boot', cv2.resize( np.array(rg, 'uint8'),(w,h)) )
            # cv2.waitKey( 0 )
            rg[(RGBmean < minVal) ]=255 #255 = foreground
            rg[(RGBmean > maxVal) ]=255

            # & (RGBmean > maxVal)
            rg =  np.where(rg>0 , rg, -1*rg)
            # cv2.imshow('boot', cv2.resize( np.array(rg, 'uint8'),(w,h)))
            # cv2.waitKey( 0 )
            rg[rg < drawing_setting['-GRAY CONST-'] ] = 0 #0 = gray background
            # cv2.imshow('boot', cv2.resize( np.array(rg, 'uint8'),(w,h)))
            # cv2.waitKey( 0 )
            rg[rg >= drawing_setting['-GRAY CONST-'] ] = 255
            # cv2.imshow('boot', cv2.resize( np.array(rg, 'uint8'),(w,h)))
            # cv2.waitKey( 0 )
            # rg = np.where(R>230 , 255, np.subtract(R,G))
            # rg[rg < drawing_setting['-GRAY CONST-'] ] = 255
            #rg = cv2.max(rg,0)
            rb = RGB16+R-B  #np.subtract(R,B)
            # rg = np.where(R<100 , R, np.subtract(R,G))
            # rg = np.where(R>230 , R, np.subtract(R,G))
            # rb[(RGBmean < minVal) & (RGBmean > maxVal)]=255
            rb[(RGBmean < minVal) ]=255
            rb[(RGBmean > maxVal) ]=255
            rb =  np.where(rb>0 , rb, -1*rb)
            rb[rb < drawing_setting['-GRAY CONST-'] ] = 0 #(0,0,0)
            rb[rb >= drawing_setting['-GRAY CONST-'] ] = 255 #(0,0,0)
            #rb = cv2.max(rb,0)
            add = cv2.add(rg,rb)
            add = np.array(add, 'uint8')
            add = cv2.bitwise_not(add)
            add = np.where(diff_from_orig > 0  ,add_diff, add )
        
        # add = 
        # add = np.where(R>230 , 0, add)
        #add[R<100 and R>230] = 0
        #cv2.imshow('boot', cv2.resize(add,(w,h)))
        #cv2.waitKey( 0 )

        #add [add < drawing_setting['-THRESH SIMPLE-'] ] = 0
        #add [add >= drawing_setting['-THRESH SIMPLE-'] ] = 255
        _,readymask = cv2.threshold( add, 240, 255, cv2.THRESH_BINARY)

        #readymask = add
        frame = readymask
        if not (no_show):
            cv2.imshow('boot', cv2.resize(readymask,(w,h)))
            cv2.waitKey( show_speed )
    elif forest_only :
        #bl = int(drawing_setting['-BLUR VALUE-'])
        #frame = cv2.GaussianBlur(frame, (5, 5), 0)
        blurred = cv2.GaussianBlur(frame, (5, 5), 0)
        blurred_float = blurred.astype(np.float32) / 255.0
        # newfp = np.memmap('tmpdiskarr.dat', dtype='float32', mode='w+', shape=frame.shape)
        # newfp[:] = blurred_float[:]
        # del blurred_float
        edgeDetector = cv2.ximgproc.createStructuredEdgeDetection("model.yml")
        edges = edgeDetector.detectEdges(blurred_float) * 255.0
        # del newfp
        readymask =  cv2.bitwise_not( np.asarray(edges, np.uint8) )
        del edges
        del blurred
        del blurred_float
        _,readymask = cv2.threshold( readymask, drawing_setting['-THRESH SIMPLE-'], 255, cv2.THRESH_BINARY)
        frame = readymask
        if not (no_show):
            cv2.imshow('boot', cv2.resize(readymask,(w,h)))
            cv2.waitKey( show_speed )


    else :
        #frame = cv2.convertScaleAbs(frame, alpha=alpha, beta=beta)
        resized = cv2.resize(frame, (w, h) )
        #cv2.imshow('boot', resized)
        #cv2.waitKey( 1000 )


        if drawing_setting['-NOISE-'] :
            frame = filterOutSaltPepperNoise(frame)

    mainImageID = set_canvas_image (frame, graph, mainImageID, w, h)
    return frame, mainImageID, w, h, readymask

def apply_part2 (imgsrc, drawing_setting, graph,w,h,windowTitle, only_bright = False, no_show = False, save_mask = False, readymask = None, grabcut = False, interactive_mask_add = None): #contours  w,h = resized

    alpha = drawing_setting['-ALPHA-'] / 100
    beta = drawing_setting['-BETA-'] - 100
    img = cv2.convertScaleAbs(imgsrc, alpha=alpha, beta=beta)
    #lightened preview
    #cv2.imshow('boot', cv2.resize( img, (w,h) ))
    #cv2.waitKey( 1000 )
    # cv2.imshow('boot', cv2.resize( readymask, (w,h) ))
    # cv2.waitKey( 0 )
    if drawing_setting['-SHOW SPEED-'] == 0: 
        show_speed = 1
    else:
        show_speed = int (drawing_setting['-SHOW SPEED-'])

    hsrc, wsrc, chsrc = img.shape
    drawings = graph.TKCanvas.find_all()
    grabcut_colors = False
    if readymask is None :
        readymask = None
        contourImg = grab_screen (graph, w, h, windowTitle)
        contourImgGray = cv2.cvtColor( contourImg  , cv2.COLOR_BGR2GRAY);
    else :
        if len( drawings )>1 :
            mask_color = np.zeros( img.shape, np.uint8 ) 
            for fig in sorted(drawings) : #assume later on top
                figtype = graph.TKCanvas.type(fig)
                if figtype == 'line' or figtype == 'oval' or figtype == 'rectangle':
                    width = int(4*wsrc/w) #thinner than on canvas
                    x1,y1,x2,y2 = graph.TKCanvas.coords(fig)
                    x1,y1 = real_xy (img.shape, w, h, x1, y1)
                    x2,y2 = real_xy (img.shape, w, h, x2, y2)
                    color = graph.TKCanvas.itemcget(fig,"fill")
                    if color == '' :
                        color = graph.TKCanvas.itemcget(fig,"outline") #green

                    if color == 'black' :
                        fcolor = (0,0,0)
                    elif color == 'red' :
                        grabcut_colors = True
                        fcolor = (0,0,255) #BGR
                    elif color == 'green' :  
                        grabcut_colors = True
                        fcolor = (0,255,0) #BGR
                    elif color == 'blue' :
                        grabcut_colors = True
                        fcolor = (255,0,0) #BGR
                    else:
                        fcolor = (255,255,255)
                    
                    if figtype == 'oval' :
                        centerx = int((x2-x1)/2) + x1
                        centery = int((y2-y1)/2) + y1
                        radius = int((x2-x1)/2)
                        if (color == 'red') or (color == 'blue') or (color == 'green'):
                            mask_color = cv2.circle(mask_color,(centerx,centery),radius,fcolor,-1)
                        else:
                            readymask = cv2.circle(readymask,(centerx,centery),radius,fcolor,-1)
                    elif figtype == 'line':
                        if (color == 'red') or (color == 'blue') or (color == 'green'):
                            mask_color = cv2.line(mask_color,(x1,y1),(x2,y2),fcolor,width)
                        else:
                            readymask = cv2.line(readymask,(x1,y1),(x2,y2),fcolor,width)
                    else : #rect
                        if (color == 'red') or (color == 'blue') or (color == 'green'):
                            mask_color = cv2.rectangle(mask_color,(x1,y1),(x2,y2),fcolor,-1)
                        else:
                            readymask = cv2.rectangle(readymask,(x1,y1),(x2,y2),fcolor,-1)
            # cv2.imshow('boot', cv2.resize( mask_color, (w,h) ))
            # cv2.waitKey( 0 )
        if not interactive_mask_add is None:
            #add from interactive mask (priority above readymask)
            readymask[interactive_mask_add == 0] = 0
            readymask[interactive_mask_add == 128] = 255
            readymask[interactive_mask_add == 255] = 255
        contourImg = cv2.cvtColor( readymask  , cv2.COLOR_GRAY2BGR) 
        contourImgGray = readymask
    #end of readymask <> NONE

    contour = findSignificantContour(cv2.bitwise_not(contourImgGray))
    # cv2.imshow('boot', cv2.resize( readymask, (w,h) ))
    # cv2.waitKey( 0 )
    # cv2.imshow('boot', cv2.resize( contourImg, (w,h) ))
    # cv2.waitKey( 0 )
    #filledcontours
    cv2.drawContours(contourImg, [contour], 0, (0,255,0), -1)#, cv2.LINE_AA, maxLevel=1)
    maskByContour = cv2.inRange(contourImg, (0,254,0),(0,255,0))
    if not (no_show):
        cv2.imshow('boot', cv2.resize( contourImg, (w,h) ))
        cv2.waitKey( show_speed )
    if grabcut :
        #increase edges
        maskByContour_inv = cv2.bitwise_not(maskByContour)
        decreased_mask = cv2.erode(maskByContour, np.ones((5, 5), np.uint8), iterations=3)
        increased_mask = cv2.dilate(maskByContour, np.ones((5, 5), np.uint8), iterations=10)
        # cv2.imshow('boot', cv2.resize( maskByContour, (w,h) ))
        # cv2.waitKey( 0 )
        # cv2.imshow('boot', cv2.resize( decreased_mask, (w,h) ))
        # cv2.waitKey( 0 )
        # cv2.imshow('boot', cv2.resize( increased_mask, (w,h) ))
        # cv2.waitKey( 0 )
        maskPBG = increased_mask - decreased_mask #PBG = probably background
        # cv2.imshow('boot', cv2.resize( maskPBG, (w,h) ))
        # cv2.waitKey( 0 )

        #grabcut exits if image is too big, so make roi
        xm,ym,wm,hm = cv2.boundingRect(maskPBG)
        if xm+wm > wsrc :
            wm = wsrc-xm
        if ym+hm > hsrc :
            hm = hsrc-xm

        if not (no_show):
            tmpimg = np.copy(img)
            tmpimg = cv2.rectangle(tmpimg,(xm,ym),(xm+wm,ym+hm),(255,0,0),5) #blue rect
            cv2.imshow('boot', cv2.resize( tmpimg, (w,h) ))        
            cv2.waitKey( 10 )
            del tmpimg

        img2 = img[ym:ym+hm,xm:xm+wm]
        maskPBG2 = maskPBG[ym:ym+hm,xm:xm+wm]
        increased_mask2 = increased_mask[ym:ym+hm,xm:xm+wm]
        decreased_mask2 = decreased_mask[ym:ym+hm,xm:xm+wm]
        # cv2.imshow('boot', cv2.resize( maskPBG2, (w,h) ))
        # cv2.waitKey( 0 )
        # maskByContour2 = maskByContour[ym:ym+hm,xm:xm+wm]

        trimap = np.copy(decreased_mask2)
        trimap[increased_mask2 == 0] = cv2.GC_BGD
        trimap[maskPBG2 == 255] = cv2.GC_PR_BGD
        trimap[decreased_mask2 == 255] = cv2.GC_FGD

        if grabcut_colors :
            mask_color2 = mask_color[ym:ym+hm,xm:xm+wm]
          
            # tmp = np.zeros(increased_mask.shape, np.uint8)
            # tmp[ym:ym+hm,xm:xm+wm] = trimap 
            # # trimap_print = tmp[1300:2200,1200:1800]
            # trimap_print = tmp
            # trimap_print[trimap_print == cv2.GC_PR_BGD] = 128
            # trimap_print[trimap_print == cv2.GC_FGD] = 255        
            # cv2.imshow('boot', cv2.resize( trimap_print, (w,h) ))
            # cv2.waitKey( 0 )
            
            trimap[mask_color2[:,:,2] == 255] = cv2.GC_FGD #blue
            trimap[mask_color2[:,:,1] == 255] = cv2.GC_PR_BGD #green
            trimap[mask_color2[:,:,0] == 255] = cv2.GC_BGD #red
            
            # if not (no_show):
            # # visualize trimap for colored mask
            #     trimap_print = np.zeros(increased_mask.shape, np.uint8)
            #     trimap_print[ym:ym+hm,xm:xm+wm] = trimap 
            #     #trimap_print = tmp[1300:2200,1200:1800]
            #     trimap_print[trimap_print == cv2.GC_PR_BGD] = 128
            #     trimap_print[trimap_print == cv2.GC_FGD] = 255        
            #     cv2.imshow('boot', cv2.resize( trimap_print, (w,h) ))
            #     cv2.waitKey( 0 )


        # visualize trimap
        #  trimap_print = np.copy(trimap)
        #  trimap_print[trimap_print == cv2.GC_PR_BGD] = 128
        #  trimap_print[trimap_print == cv2.GC_FGD] = 255        
        #  cv2.imshow('boot', cv2.resize( trimap_print, (w,h) ))
        #  cv2.waitKey( 0 )
        
        bgdModel = np.zeros((1, 65), np.float64) #65???
        fgdModel = np.zeros((1, 65), np.float64)

        #rect = cv2.boundingRect(maskPBG)
        gc_iterations = int(drawing_setting['-GRABCUT COUNT-']) 
        try :
            #if program quits than image too big? memory alloc?
            cv2.grabCut(img2, trimap, None, bgdModel, fgdModel, gc_iterations, cv2.GC_INIT_WITH_MASK)
        except:
            import traceback
            traceback.print_exc()
            
        mask2 = np.where(  
                (trimap == cv2.GC_FGD) | (trimap == cv2.GC_PR_FGD)
                #(trimap == cv2.GC_FGD)
                ,255
                ,0    ).astype('uint8')
        maskByContour = np.zeros(maskByContour.shape, np.uint8)
        contourImg = np.zeros(img.shape, np.uint8) 
        maskByContour[ym:ym+hm,xm:xm+wm] = mask2

        #second time after grabcut
        contour = findSignificantContour(maskByContour)
        cv2.drawContours(contourImg, [contour], 0, (0,255,0), -1)#, cv2.LINE_AA, maxLevel=1)
        maskByContour = cv2.inRange(contourImg, (0,254,0),(0,255,0))

        if not (no_show):
            cv2.imshow('boot', cv2.resize( maskByContour, (w,h) ))
            cv2.waitKey( show_speed )
        del trimap; del img2; del mask2; del maskPBG; del maskPBG2
        del increased_mask; del increased_mask2; del decreased_mask; del decreased_mask2;


    if readymask is None:
        maskByContour = cv2.resize (maskByContour, (wsrc,hsrc))
        _,maskByContour = cv2.threshold(maskByContour,254,255,cv2.THRESH_BINARY ) #clean resize artefacts
    #cv2.imshow('boot', cv2.resize( maskByContour, (w,h) ))
    #cv2.waitKey( 0 )

    #fix sides on crop-resize
        #roi [y:x]   if range then 0:maxrange, if single value then maxrange-1
    roil = maskByContour[0:hsrc,0]
    roir = maskByContour[0:hsrc,wsrc-1]
    roit = maskByContour[0,0:wsrc]
    roib = maskByContour[hsrc-1,0:wsrc]
    fix_left   = cv2.mean( roil  )[0] > 0    #black(=0) mask=0 no objects, empty, no need to fix
    fix_right  = cv2.mean( roir  )[0] > 0
    fix_top    = cv2.mean( roit  )[0] > 0
    fix_bottom = cv2.mean( roib  )[0] > 0
    # cv2.imwrite('mask.jpg', maskByContour)
    # cv2.imwrite('l.jpg', roil)
    # cv2.imwrite('r.jpg', roir)
    # cv2.imwrite('t.jpg', roit)
    # cv2.imwrite('b.jpg', roib)

    maskByContour_inv = cv2.bitwise_not(maskByContour)
    imgnew = np.copy(img)
    # cv2.imshow('boot', cv2.resize(img, (w,h) ))
    # cv2.waitKey( 0 )
    if only_bright == False:

        # p2 = maskByContour[1400:1420, 800:850]
        # cv2.imshow('boot', p2)
        # cv2.waitKey( 0 )
        # p2 = maskByContour_inv[1400:1420, 800:850]
        # cv2.imshow('boot', p2)
        # cv2.waitKey( 0 )
        ozongray = (245,243,242)
        grayed = np.zeros(img.shape, np.uint8)
        grayed[:] = ozongray
        imgnewFG = cv2.bitwise_and( img, img, mask = maskByContour )
        # p2 = imgnewFG[1400:1420, 800:850]
        imgBGozon = cv2.bitwise_and( grayed, grayed, mask = maskByContour_inv )
        # p2 = imgnewBG[1400:1420, 800:850]
        # cv2.imshow('boot', p2)
        # cv2.waitKey( 0 )
        # p2 = cv2.add(imgnewFG, imgnewBG)[1400:1420, 800:850]
        # cv2.imshow('boot', p2)
        # cv2.waitKey( 0 )
    
        # cv2.imshow('boot', cv2.resize( imgnewBG, (w,h) ))
        # cv2.waitKey( 4000 )
        # cv2.imshow('boot', cv2.resize( cv2.add(imgnewFG, imgnewBG), (w,h) ))
        # cv2.waitKey( 4000 )

        #if drawing_setting['-OZONGRAY-'] >0 :
        
        #light background by mean of right center square 50x50
        y1,y2 = int(hsrc/2)-50, int(hsrc/2)+50
        x1,x2 = wsrc-50,wsrc
        roi = img[y1:y2,x1:x2]
        result, alpha, beta = alpha_beta_bymean (roi, 254, maxcounter = 150, alpha_mult=1)
        if result:
            imgBG = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)
        imgBG = cv2.bitwise_and( img, img, mask = maskByContour_inv )

        #cv2.imshow('boot', cv2.resize(imgBGozon, (w,h) ))
        #cv2.waitKey( 0 )
        #cv2.imshow('boot', cv2.resize(imgBG, (w,h) ))
        #cv2.waitKey( 0 )
        
        imgnewBG = cv2.addWeighted(imgBG,drawing_setting['-OZONGRAY-'],imgBGozon,1 - drawing_setting['-OZONGRAY-'],0)
        #cv2.imshow('boot', cv2.resize(imgnewBG, (w,h) ))
        #cv2.waitKey( 0 )

        imgnew = cv2.add(imgnewFG,imgnewBG)
        #cv2.imshow('boot', cv2.resize(imgnew, (w,h) ))
        #cv2.waitKey( 0 )

        if drawing_setting['-BLUREDGES-'] :
            #add blur edges
            blurred_img = cv2.GaussianBlur(imgnew, (5, 5), 0)
            blurred_mask = np.zeros(contourImg.shape, np.uint8)
            cv2.drawContours(blurred_mask, [contour], 0, (255,255,255), 2, cv2.LINE_AA, maxLevel=1)
            blurred_mask = cv2.resize (blurred_mask, (wsrc,hsrc))
            imgnew = np.where(blurred_mask==np.array([255, 255, 255]), blurred_img, imgnew)

    #crop to ozon size
    xr,yr,wr,hr = cv2.boundingRect(maskByContour)
    imgnew = format_1200_1500 (imgnew, xr,yr,wr,hr, (fix_left, fix_right, fix_top, fix_bottom) )
    if save_mask:
        mask_cropped = format_1200_1500 (maskByContour, xr,yr,wr,hr, (fix_left, fix_right, fix_top, fix_bottom) )
        img_bright = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)
        img_bright = format_1200_1500 (img_bright, xr,yr,wr,hr, (fix_left, fix_right, fix_top, fix_bottom) )
        cv2.imwrite("tmpmask.png", mask_cropped)
        cv2.imwrite("tmpimage.png", img_bright)

    contourImg2 = cv2.resize(imgnew, (600,750) ) #src resize
    #contourImg2 = cv2.resize(imgnew, (w,h) ) #src resize
    if not (no_show):
        cv2.imshow('boot', contourImg2)
    #cv2.waitKey( 0 )
    

    #sat light 
    # imgnew = cv2.cvtColor(imgnew, cv2.COLOR_BGR2HSV)
    # if int(values['-HSVS-']) > 0 : 
    #     imgnew[:, 0, :] += int(values['-HSVS-'])
    # if int(values['-HSVV-']) > 0 : 
    #     imgnew[0, :, :] += int(values['-HSVV-'])
    # imgnew = cv2.cvtColor(imgnew, cv2.COLOR_HSV2BGR)
    return imgnew, maskByContour_inv

# def apply_brightness_contrast (img, drawing)
#     alpha = drawing_setting['-ALPHA-'] / 100
#     beta = drawing_setting['-BETA-'] - 100
#     img = cv2.convertScaleAbs(imgsrc, alpha=alpha, beta=beta)
#     imgnew = format_1200_1500 (imgnew, xr,yr,wr,hr,drawing_setting)
#     contourImg2 = cv2.resize(imgnew, (w,h) ) #src resize
#     cv2.imshow('boot', contourImg2)
#     return imgnew
def real_xy(imgshape, canvas_w, canvas_h, x, y):
    hsrc, wsrc = imgshape[:2]
    if x< 0 :
        x =0
    if y< 0 :
        y =0
    if x> canvas_w :
        x =canvas_w
    if y> canvas_h :
        y =canvas_h

    realx = int(wsrc/canvas_w * x)
    realy = int(hsrc/canvas_h * y)
    if realy > hsrc-1 : 
        realy = hsrc-1
    if realx > wsrc-1 : 
        realx = wsrc-1
    return realx,realy


def change_folder(window):
    event, values = window.read(timeout=0)
    folder = values['-FOLDER-']
    folder_out = values['-FOLDER OUT-']
    if not (os.path.exists(folder_out)) :
        os.mkdir(folder_out)
    if folder[-1] != '/':
        folder = folder + '/'
        window['-FOLDER-'].update (folder)
    if folder_out[-1] != '/':
        folder_out = folder_out + '/'
        window['-FOLDER OUT-'].update (folder_out)
    folder_out_manual = values['-FOLDER OUT-']+"manual/"
    if not (os.path.exists(folder_out_manual)) :
        os.mkdir(folder_out_manual)
    try:
        file_list_in = os.listdir(folder)         # get list of files in folder
        # file_list_out = os.listdir(folder_out)         # get list of files in folder
        # file_list_out_manual = os.listdir(folder_out_manual)         # get list of files in folder
        file_list_out =[]
        for address, dirs, files in os.walk(folder_out): #all
            for ffile in files:
                file_list_out.append(ffile)
    except:
        file_list_in = []
    fnames = []
    for f in file_list_in :
        if ( os.path.isfile( os.path.join(folder, f) ) 
             and f.lower().endswith((".png", ".jpg", ".jpeg", ".tiff", ".bmp")) 
             and not (f.replace('.JPG','.jpg') in file_list_out)  ):
             #and not (f.replace('.JPG','.jpg') in file_list_out_manual) ) :
                fnames.append(f.replace('.JPG','.jpg') ) #need lower .jpg
    window['-FILELIST-'].update(fnames)
    pass
    
def change_file (window, graph):
    event, values = window.read(timeout=1000)
    file_chosen = False
    img = None
    try:
        fname = values['-FILELIST-'][0]
        folder = values['-FOLDER-']
        if fname == '':
            fname = fname_default
        window['-FILENAME-'].update( fname )
        
        # filename = os.path.join(values['-FOLDER-'], fname ) #opencv does not open cyrillic
        script_path = os.getcwd()
        os.chdir(folder)
        img = cv2.imread(fname)
        os.chdir(script_path)
        if img is None:
            print('File not opened: ', fname)
            exit(0)
        graph.erase() #clean previous drawing for mask
        file_chosen = True
    except Exception as E:
        print(f'** Error {E} **')
        pass        # something weird happened making the full filename
    return file_chosen, img

def format_1200_1500 (img,x1,y1,w1,h1,fixsides = (False, False, False, False)):
    #get minimal rect
    h = img.shape[0]
    w = img.shape[1]
    w_dest = 1200 
    h_dest = 1600  #1600 = wildberries 3:4 , 1500 = ozon 4:5
    if w/h > 1 :
        padding_x = 200
        padding_y = 100
    else :
        padding_x = 100
        padding_y = 200
    x1, y1, x2, y2 = x1-padding_x, y1-padding_y, x1+w1+padding_x, y1+h1+padding_y

    if x1 < 0 : x1 = 0
    if y1 < 0 : y1 = 0
    if x2 > w : x2 = w
    if y2 > h : y2 = h
    
    #x1,y1 x2,y2 - minimal rect
    #need to stretch to 1200 x 1500 = 4:5
    w_current = x2 - x1
    h_current = y2 - y1

    add_border_top, add_border_bottom, add_border_left, add_border_right = 0,0,0,0
    # t1 = cv2.rectangle(img,(x1,y1),(x2,y2),(0,255,0),10)
    # cv2.imshow('boot', cv2.resize(t1, (958,639) ))
    # cv2.waitKey( 0 )

    #crop to aspect 
    if w_current < w_dest and h_current < h_dest :  
        #smaller -> get borders from image =  smaller src crop to bigger
        h_needed = h_dest
        w_needed = w_dest
    if w_current == w and h_current == h : 
        # all fixed, crop image with loose
        if  w / w_dest > h / h_dest :  #h_current = h #w_current = w
            #w ratio > h ratio - w need to be smaller
            h_needed = h
            w_needed = int(  h * w_dest / h_dest ) 
            #2021-08 - do not crop
            if w_needed < w_current :   #w_current=w
                h_needed = int(  w * h_dest / w_dest )
                w_needed = w
        else :
            w_needed = w
            h_needed = int(  w * h_dest / w_dest ) 
    elif w_current == w :
        #fixl,r - need to do w or h smaller, crop image with loose
        #try to get maximum of h
        h_needed = int(  w * h_dest / w_dest )
        if h_needed < h :
            w_needed = w
        else:
            #maximize h
            if  w / w_dest > h / h_dest : 
                #w ratio > h ratio - w need to be smaller
                
                #2021-08 not crop, not minimize h_needed
                #h_needed = h
                #w_needed = int(  h_needed * w_dest / h_dest )
                w_needed = w
            else :
                w_needed = w
                h_needed = int(  w * h_dest / w_dest ) 
    elif w_current / w_dest == h_current / h_dest :  
        #aspect ok -> resize to smaller
        h_needed = h_dest
        w_needed = w_dest
    elif w_current / w_dest > h_current / h_dest :
        #w or h > dest
        #w/wdest > h/hdest -> need to raise h else raise w
        
        #logic:
            #aspect_needed = w_current / w_dest
            #aspect_low = h_current / h_dest
            #h_needed = int( h_current / aspect_low * aspect_needed )
        #simplify fomula:
        h_needed = int(  w_current * h_dest / w_dest )
        w_needed = w_current
    else:
        w_needed = int(  h_current * w_dest / h_dest )
        h_needed = h_current
    

    if w_current == w : #2021-08
        #bottom left corner
        x1,x2 = 0, 0+w_needed
    if h_current == h :
        y1,y2 = h-h_needed, h
        if y1<0 : 
            y1 = 0 
    # if w_current == w and h_needed < h_current: #2021-08 добавил условие h_needed < h_current
    #     #bottom left corner
    #     x1,x2 = 0, 0+w_needed
    #     y1,y2 = h-h_needed, h 
    #elif h_needed > h_current:
    if h_needed != h_current:
        #h_needed > h_current -> pad y1
        diff2 = int( (h_needed - h_current)/2 ) 
        y1_new = y1 - diff2
        y2_new = y2 + diff2
        #how much out of border (plus = out of border)
        d1 = 0 - y1_new
        d2 = y2_new - h
        if d1 > 0 : 
            y1 = 0
            add_border_top = d1
        else :
            y1 = y1_new
            add_border_top = 0 
        if d2 > 0 :
            y2 = h
            add_border_bottom = d2
        else :
            y2 = y2_new  
            add_border_bottom = 0 
    if w_needed != w_current : 
        #w_needed > w_current -> pad x1
        diff2 = int( (w_needed - w_current)/2 ) 
        x1_new = x1 - diff2
        x2_new = x2 + diff2
        #how much out of border (plus = out of border)
        d1 = 0 - x1_new
        d2 = x2_new - w
        if d1 > 0 : 
            x1 = 0
            add_border_left = d1
        else :
            x1 = x1_new
        if d2 > 0 :
            x2 = w
            add_border_right = d2
        else :
            x2 = x2_new

    # #check if enters image
    # if w_needed > w : 
    #     diff = (x1 + w_needed) - w
    #     diffx = int( diff/2 )
    #     x2 = w
    # else :
    #     x2 = x1 + w_needed
    #     diffx = 0
    # if y1 + h_needed > h : 
    #     diff = (y1 + h_needed) - h
    #     diffy = int( diff/2 )
    #     y2 = h
    # else :
    #     y2 = y1 + h_needed
    #     diffy =0

    # t1 = cv2.rectangle(img,(x1,y1),(x1+w_needed,y1+h_needed),(0,0,255),10)
    # cv2.imshow('boot', cv2.resize(t1, (958,639) ))
    # cv2.waitKey( 0 )

    #get part of image, add borders    
    roi = img[y1:y2,x1:x2]

    # t1 = cv2.rectangle(img,(x1,y1),(x2,y2),(0,255,0),10)
    # cv2.imshow('boot', cv2.resize(t1, (599,449) ))
    # cv2.waitKey( 0 )

    #top, bottom, left, right = diffy, diffy, diffx, diffx
    fixl, fixr, fixt, fixb = fixsides
    if not (fixl and fixr and fixt and fixb) :
        if fixl :
            add_border_right = add_border_right + add_border_left
            add_border_left = 0
        if fixr :
            add_border_left =  add_border_left + add_border_right
            add_border_right = 0
        if fixt :
            add_border_bottom = add_border_bottom + add_border_top
            add_border_top = 0
        if fixb :
            add_border_top = add_border_top + add_border_bottom
            add_border_bottom = 0

    newimg = cv2.copyMakeBorder (roi, add_border_top, add_border_bottom, add_border_left, add_border_right, cv2.BORDER_REPLICATE)
    h_new = newimg.shape[0]
    w_new = newimg.shape[1]
    if (h_new > h_dest) or (w_new > w_dest) :
        newimg = cv2.resize (newimg, (w_dest,h_dest))
    return newimg

def saveFile (img_to_save, filename, folderout, listbox_element, window, graph):
    script_path = os.getcwd()
    os.chdir(folderout)
    cv2.imwrite( filename.replace('.JPG', '.jpg'), img_to_save )
    os.chdir(script_path)
    #change listbox to next
    curr_select = listbox_element.curselection()
    if len(curr_select) > 0 : #array
        last_in_selection = int( curr_select[-1] )
        next_one = last_in_selection + 1
        if next_one < listbox_element.size() :
            listbox_element.selection_clear(curr_select)
            listbox_element.activate (next_one)
            listbox_element.selection_set (next_one)
            file_chosen,img = change_file (window, graph)
            next_one_selected = True
        else:
           file_chosen = None; img = None; next_one_selected = False 
    return file_chosen, img, next_one_selected

def open_interactive(roi):
    window_wmax = 600
    window_hmax = 800
    wi, hi, _ = ResizeWithAspectRatio ( roi.shape, window_wmax, window_hmax) 
        
    layout3 = [
                [
                    sg.Radio('background', 'IColor', size=(10, 1), key='-IWHITE-',  enable_events=True),
                    sg.Radio('foreground', 'IColor', size=(10, 1), key='-IBLACK-', default = True,  enable_events=True),
                    sg.Radio('grey area', 'IColor', size=(10, 1), key='-IGRAY-',  enable_events=True),
                ],
                [
                    sg.Radio('line', 'ITool', size=(10, 1), key='-ILINE-',  enable_events=True),
                    sg.Radio('point', 'ITool', size=(10, 1), key='-IPOINT-', default = True,  enable_events=True),
                    sg.Radio('fill mask', 'ITool', size=(10, 1), key='-IFILL-',  enable_events=True),
                    sg.Radio('fill quantized', 'ITool', size=(10, 1), key='-IFILLQ-',  enable_events=True),
                ],
                [   
                    sg.Text('quant colors:'), sg.Slider(range=(1, 20), orientation='h', size=(10, 20), default_value=8, key = '-IQCOLORS-',enable_events=True ),
                    sg.Checkbox('clahe', default = False, key='-ICLAHE-', enable_events=True ), 
                ],
                [   
                    sg.Text('width line/point:'), sg.Slider(range=(1, 20), orientation='h', size=(10, 20), default_value=4, key = '-IWIDTH-'),
                    sg.Text(' '*10),
                    sg.Checkbox('auto grabcut', default = False, key='-AUTO GRABCUT-' ), 
                    sg.Button('Do grabcut'),
                    sg.Button('Simple mask'),
                    sg.Button('Undo step',  key='-UNDOSTEP-', disabled=True),
                ],
                [sg.Text('_'*30)  ,],
                [
                    sg.Button('Show mask', key='-IMASK-'),
                    sg.Button('Show mask/img', key='-IMASKIMG-'),
                    sg.Button('Show img',  key='-IIMG-'),
                    sg.Button('Show result',  key='-IIMGRESULT-'),
                ],
                [sg.Text('_'*30) ,],
                [
                    sg.Button('Apply mask'),
                    sg.Button('Reset mask'),
                    sg.Button('Cancel'),
                ],
                [],
                [sg.Text('drag with mouse button = line, point = fill',key ='-IINFO-' ), ],
                [sg.Graph(
                canvas_size=(wi, hi),
                graph_bottom_left=(0, hi),
                graph_top_right=(wi, 0),
                key="-IGRAPH-",
                enable_events=True,
                background_color='white',
                drag_submits=True) ] ,
             ]

    window3 = sg.Window('Interactive mask edit', layout3, finalize=True)
    window3['-IGRAPH-'].bind('<Button-3>', '+RIGHT+')

    resized = cv2.resize(roi, (wi, hi) )
    imgbytes = cv2.imencode('.png', resized)[1].tobytes()
    #window3['-IGRAPH-'].delete_figure(mainImageID)             # delete previous image
    iMainImageID = window3['-IGRAPH-'].draw_image(data=imgbytes, location=(0,000))    # interactive ID
    #window3[-IGRAPH-].TKCanvas.tag_lower(mainImageID)           # move image to the "bottom" of all other drawings

    if window3.current_location()[0]<0 :
        newx = 50
    else: 
        newx = window3.current_location()[0]
    if window3.current_location()[1]<0 :
        newy = 50
    else: 
        newy = window3.current_location()[1]
    window3.move(newx,newy)

    return window3, iMainImageID, wi, hi

def grabcut_onbwgray(img, mask):
        trimap = np.copy(mask)
        trimap[mask == 255] = cv2.GC_BGD
        trimap[mask == 128] = cv2.GC_PR_BGD
        trimap[mask == 0] = cv2.GC_FGD
        bgdModel = np.zeros((1, 65), np.float64) #65???
        fgdModel = np.zeros((1, 65), np.float64)
        gc_iterations = 5
        try :
            #if program quits than image too big? memory alloc?
            cv2.grabCut(img, trimap, None, bgdModel, fgdModel, gc_iterations, cv2.GC_INIT_WITH_MASK)
        except:
            import traceback
            traceback.print_exc()
            
        # mask2 = np.zeros(mask.shape, np.uint8)
        # mask2 = np.where( (trimap == cv2.GC_FGD), 255 ,mask2)  
        # mask2 = np.where( (trimap == cv2.GC_PR_BGD), 128 ,mask2)  
        #128 - b
        mask2 = np.where(  
                (trimap == cv2.GC_FGD) | (trimap == cv2.GC_PR_FGD)
                ,0    
                ,255    ).astype('uint8')        

        mask3 = cv2.bitwise_not( mask2 ) #np.where( (trimap == cv2.GC_BGD), 255, 0).astype('uint8') 
        resultimg = cv2.bitwise_and( img, img, mask = mask3 )
        mask2[mask2 == 255] = 128 #init as GC_PR_BGD
        return mask2, resultimg

def set_canvas_image (img, graph, graph_imgID, resize_to_w, resize_to_h):
    resized = cv2.resize(img, (resize_to_w, resize_to_h) )
    imgbytes = cv2.imencode('.png', resized)[1].tobytes()
    if graph_imgID:
        graph.delete_figure(graph_imgID)             # delete previous image
    graph_imgID = graph.draw_image(data=imgbytes, location=(0,000))    # draw new image
    graph.TKCanvas.tag_lower(graph_imgID)           # move image to the "bottom" of all other drawings
    return graph_imgID

def quantize(img, iters = 10, epsilon = 1.0, K=8) : 
    Z = img.reshape((-1,3))
    # convert to np.float32
    Z = np.float32(Z)
    # define criteria, number of clusters(K) and apply kmeans()
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, iters, epsilon)
    ret,label,center=cv2.kmeans(Z,K,None,criteria,10,cv2.KMEANS_RANDOM_CENTERS)
    # Now convert back into uint8, and make original image
    center = np.uint8(center)
    res = center[label.flatten()]
    res2 = res.reshape((img.shape))
    return res2















def main():


    sg.theme('LightGreen')
    folder = "e:/3/1/"
    folder = "e:/!temp/фото_игрушки 05.08.2021/2/"
    folderout = "e:/3/1/out/"
    folderout = "e:/!temp/фото_игрушки 05.08.2021/2/out/"

    if not (os.path.exists(folder)) :
        folder = os.getcwd()
        folderout = folder + "/out/"
        print ('Folder not defined. Using default')
    
    # fns = "W:/Работа/1s/Инвенто/25.11.2020/out/03A-3083.jpg"
    # script_path = os.getcwd()
    # os.chdir(folder)
    # fn = '03A-3083.jpg'
    # ttt = cv2.imread(fn)
    # os.chdir(script_path)
    # # print (os.listdir())
    # if ttt is None:
    #     print ('None')
    # exit(0)

    # define the window layout
    layout2 = [
        [sg.Text('In folder' ), sg.Input(folder,key='-FOLDER-', size=(45, 1), enable_events=True),sg.FolderBrowse()],
        [sg.Text('Out folder'), sg.Input(folderout,key='-FOLDER OUT-', size=(45, 1)),sg.FolderBrowse()],
        [sg.Checkbox ('Bright', default = True, key='-BRIGHTNESS-' ), 
         sg.Slider((0, 250), 100, 1, orientation='h', size=(20, 15), key='-ALPHA-', enable_events=True),
         sg.Checkbox ('Autodetect', default = False, key='-AUTOBRIGHTNESS-' )],
        [sg.Checkbox ('Contrast', default = True, key='-CONTRAST-' ), 
         sg.Slider((0, 255), 100, 1, orientation='h', size=(20, 15), key='-BETA-', enable_events=True)],
        [sg.Checkbox ('blur', default = False, key='-BLUR-' ), 
         sg.Slider((0, 255), 5, 1, orientation='h', size=(20, 15), key='-BLUR VALUE-' ), 
         sg.Checkbox ('clahe contrast', default = False, key='-CLAHE-' ),
         sg.Slider((1, 100), 4, 1, orientation='h', size=(10, 15), key='-CLAHE1-' ), 
         sg.Slider((1, 100), 8, 1, orientation='h', size=(10, 15), key='-CLAHE2-' ), 
        ],
        [#sg.Text('bilateral', 'Radio', size=(10, 1), key='-BILATERAL-'),
         sg.Checkbox ('bilateral filter', default = False, key='-BILATERAL-' ),
         sg.Slider((0, 255), 30, 1, orientation='h', size=(20, 15), key='-BILATERAL COLOR-' ),
         sg.Slider((1, 50), 5, 1, orientation='h', size=(20, 15), key='-BILATERAL SPACE-' )],
        [ sg.Frame('Threshold:',[
                    [sg.Checkbox ('', default = False, key='-THRESH-' ),
                    sg.R('Adaptive Gauss', 10,  key='-ADAPTIVE GAUSS-',default = True), 
                    sg.R('Adaptive Mean', 10,  key='-ADAPTIVE MEAN-'), ], 
                    [sg.Text('radius'), sg.Slider((3, 150), 111, 1, orientation='h', size=(10, 15), key='-THRESH RADIUS-' ),
                    sg.Text('const'), sg.Slider((1, 50), 2, 1, orientation='h', size=(10, 15), key='-THRESH CONST-' ),
                    sg.R('Simple', 10,  key='-SIMPLE-'), #sg.Text('simple'),
                    sg.Slider((1, 255), 240, 1, orientation='h', size=(15, 15), key='-THRESH SIMPLE-' )],
                  ],
                 )     
         ],
        [ sg.Frame('Gray:',[
                    [sg.R('By mean', 10,  key='-DARKONGRAY-'),  
                    sg.Slider((0, 100), 20, 1, orientation='h', size=(10, 15), key='-GRAY CONST-' ),
                    sg.Checkbox('manual', default = False, key='-GRAY MANUAL-' ),
                    sg.Slider((100, 255), 190, 1, orientation='h', size=(15, 15), key='-GRAY MIN-' ),
                    sg.Slider((100, 255), 220, 1, orientation='h', size=(15, 15), key='-GRAY MAX-' ),],
                    [sg.Text('Vert Diff mean'),      sg.Slider((0, 100), 00, 1, orientation='h', size=(10, 15), key='-GRAY DIFF-' ),
                     sg.Text('Vert Diff std'),      sg.Slider((0, 100), 10, 1, orientation='h', size=(10, 15), key='-GRAY STD-' ),],
                    [sg.Text('center bright'),      sg.Slider((0, 2), 1, 0.1, orientation='h', size=(10, 15), key='-GRAY GRADIENT-' ),
                     sg.Text('top part darker'),    sg.Slider((0, 2), 1, 0.1, orientation='h', size=(10, 15), key='-GRAY TOPGRADIENT-' ),
                    ], 
                  ],
                 )     
         ],
        [sg.Checkbox ('noise', default = True, key='-NOISE-' ) , sg.Checkbox ('blur edges', default = True, key='-BLUREDGES-' )], 
        [sg.Text('BG to ozon gray'),sg.Slider((0, 1), 0, 0.01, orientation='h', size=(20, 15), key='-OZONGRAY-' ),
         sg.Text('grabcut count'),sg.Slider((1, 10), 2, 1, orientation='h', size=(10, 15), key='-GRABCUT COUNT-' )],
        [
         #sg.Button('1_Thresh', size=(10, 1)), 
         #sg.Button('2_Contours', size=(10, 1)), 
         sg.Button('Mask2Gimp', size=(10, 1)),
         sg.Button('Mass format', size=(10, 1)),
         sg.Button('Show image', size=(10, 1)),
         sg.Button('end image', size=(10, 1)),
         sg.Button('Show mask', size=(10, 1)),
         sg.Button('end mask', size=(10, 1)),
         ],
        [sg.Frame('Color:',[[ sg.Radio('white (gc+-, mask-)', 'RColor', size=(10, 1), key='-WHITE-',  enable_events=True),
                              sg.Radio('black (gc-, mask+)', 'RColor', size=(10, 1), key='-BLACK-', default=True, enable_events=True),
                              sg.Radio('red (gc+)', 'RColor', size=(10, 1), key='-RED-', enable_events=True),
                              sg.Radio('green (gc+-)', 'RColor', size=(10, 1), key='-GREEN-', enable_events=True),
                              sg.Radio('blue (gc-)', 'RColor', size=(10, 1), key='-BLUE-', enable_events=True),                              
                              ]], )],
        #[sg.Checkbox('Do not copy border on left', key = '-FIXL-'), sg.Checkbox('R', key = '-FIXR-'), sg.Checkbox('top', key = '-FIXT-'), sg.Checkbox('bottom', key = '-FIXB-')],
        [#left
         sg.Frame('Paint action:',[
                 [sg.R('Draw points', 1,  key='-POINT-', enable_events=True),
                  sg.R('Draw Circle', 1, key='-CIRCLE-', enable_events=True),
                  sg.R('Draw Line', 1, key='-LINE-', enable_events=True),
                  sg.R('Draw Rectangles', 1, key='-RECT-', enable_events=True)],
                 [sg.R('Erase item', 1, key='-ERASE-', enable_events=True),
                  sg.R('Erase all', 1, key='-CLEAR-', enable_events=True),
                  sg.R('Point info', 1, key='-INFO-', enable_events=True),
                  sg.R('Edit Interactive ', 1, key='-EDIT INTERACTIVE-', enable_events=True),
                  ],
                 #[sg.R('Contour fill exclude', 1,  key='-NOFILL-', enable_events=True)],
                 #[sg.R('Send to back', 1, key='-BACK-', enable_events=True)],
                 #[sg.R('Bring to front', 1, key='-FRONT-', enable_events=True)],
                 #[sg.R('Move Everything', 1, key='-MOVEALL-', enable_events=True)],
                 #[sg.R('Move Stuff', 1,  key='-MOVE-', enable_events=True)],
                 #[sg.B('Save Image', key='-SAVE-')]
                                  ],)  
        ],
         
    ]
    layout_r = [[sg.Text( size=(40, 1), key = '-FILENAME-')],
                [sg.Button('Gray remove', size=(10, 1)),  sg.Button('Forest', size=(10, 1)), sg.Button('Bright only', size=(10, 1))],
                [sg.Button('Save', size=(10, 1)),  sg.Button('Manual', size=(10, 1)), sg.Button('Exit', size=(10, 1))  ] ,
                [sg.Checkbox ('Grabcut', default = False, key='-GRABCUT-' ), sg.Text('Show speed'),sg.Slider((0, 5000), 0, 500, orientation='h', size=(10, 15), key='-SHOW SPEED-' )] ,
                [sg.Listbox( values=[], enable_events=True, size=(40,40), key = '-FILELIST-') ]
               ]

    layout_col = [[ sg.Column(layout2), sg.VSeperator(), sg.Column( layout_r ) ]]
    window2 = sg.Window('Your Palette', layout_col, finalize=True)

    #light_bar = window2['-HCL L-']
    a_bar, b_bar = window2['-ALPHA-'], window2['-BETA-']
    filelist = window2['-FILELIST-']
    lb = filelist.TKListbox

    layout1 =   [    [sg.Graph(
                canvas_size=(600, 800),
                graph_bottom_left=(0, 800),
                graph_top_right=(600, 0),
                key="-GRAPH-",
                enable_events=True,
                background_color='white',
                drag_submits=True) ] ,
                [sg.Text(key='info', size=(40, 1))] ]
    windowTitle = "Drawing and Moving Stuff Around"
    window1 = sg.Window(windowTitle, layout1, finalize=True)
    graph = window1['-GRAPH-']
  
    dragging = False
    start_point = end_point = prior_rect = None
    graph.bind('<Button-3>', '+RIGHT+')
    drawing_setting = window2.read(timeout=0)[1]

    window2.move(window1.current_location()[0]+window1.size[0], window1.current_location()[1])

    fname_default = "hor.jpg"
    fname_default = "yellow.jpg"
    #im = "light.jpg"
    #impath = folder + fname_default
    #img = cv2.imread(impath)
    #if img is None : 
    #    print(" Error opening image: " + impath )
    #    os._exit(1)

# create the form and show it without the plot
#window = sg.Window('Demo Application - Embedding Matplotlib In PySimpleGUI', layout, finalize=True, element_justification='center', font='Helvetica 18')
# add the plot to the window
#fig_canvas_agg = draw_figure(window['-CANVAS-'].TKCanvas, fig)

    # create the window and show it without the plot
#    window = sg.Window('OpenCV Integration', layout, location=(800, 400))
    
    #window = sg.Window('OpenCV Integration', layout, finalize=True, location=(800, 400), resizable= True)
    
    firstrun = True
    mainImageID= None
    resultmask = None
    interactive_mask_add = None
    point_save_mask = True
    sel_color='black'
    fill_color = sel_color
    w = 0
    last_processed_mode = 'dark'

    #frame, mainImageID, w, h  = apply_part1 (img,drawing_setting, graph, mainImageID, firstrun, a_bar, b_bar)
    #firstrun = False
    window2['-FILELIST-'].update([fname_default])
    #window, event, values = sg.read_all_windows(timeout=10)
    change_folder(window2)
    file_chosen,img = change_file (window2, graph)
    next_one_selected = False
    window_interactive = None
    while True:

        window, event, values = sg.read_all_windows()

        if event == 'Exit' or event == sg.WIN_CLOSED and not(window == window_interactive):
            break  # exit
        
        #---- interactive edit ---
        if window == window_interactive and not (event == sg.WIN_CLOSED):
            
            if values['-IWHITE-'] :
                isel_color = 'white'
                icolor = (255,255,255)
            if values['-IBLACK-'] :
                isel_color = 'black'
                icolor = (0,0,0)
            if values['-IGRAY-'] :
                isel_color = 'gray'
                icolor = (128,128,128)

            if event == 'Cancel':
                window_interactive.close()
                window_interactive = None
                imask = last_imask = before_clahe = None
            if event == 'Apply mask':
                window_interactive.close()
                window_interactive = None
                interactive_mask_add[yint1:yint2,xint1:xint2] = imask
                imask [imask > 0] = 255
                readymask[yint1:yint2,xint1:xint2]= imask #readymask will be refreshed on re-run
                mainImageID = set_canvas_image (readymask, graph, mainImageID, w, h)
                imask = last_imask = before_clahe = None
            if event == 'Reset mask':
                iMainImageID = set_canvas_image (imask_reset, igraph, iMainImageID, wi, hi)
            if event == '-UNDOSTEP-':
                if not last_imask is None:
                    imask = last_imask
                    iMainImageID = set_canvas_image (imask, igraph, iMainImageID, wi, hi)
                    window_interactive['-UNDOSTEP-'].update(disabled=True)

            if event == '-ICLAHE-':
                if values["-ICLAHE-"]:
                    before_clahe = np.copy(iimg)
                    iimg = apply_clahe (iimg, 10, 8)
                elif not (before_clahe is None) :
                    iimg = before_clahe
                if maskimg_mode == '-IIMG-':
                    iMainImageID = set_canvas_image (iimg, igraph, iMainImageID, wi, hi)
            
            if event == '-IPOINT-':
                point_save_mask = True
            if event in ('-IFILL-','-IFILLQ-','-ILINE-'):
                point_save_mask = False

            if event == '-IGRAPH-':  # if there's a "Graph" event, then it's a mouse
                x, y = values["-IGRAPH-"]
                if not dragging:
                    start_point = (x, y)
                    dragging = True
                    lastxy = x, y
                else:
                    end_point = (x, y)
                if prior_rect:
                    igraph.delete_figure(prior_rect)
                delta_x, delta_y = x - lastxy[0], y - lastxy[1]
                lastxy = x,y
                if values['-IPOINT-']:
                    if end_point is None:
                        draw_point = start_point
                    else:
                        draw_point = end_point
                    #line 
                    #linewidth = int(4*imask.shape[0]/wi)
                    linewidth=int(values["-IWIDTH-"])
                    #igraph.delete_figure(prior_rect)
                    xi1,yi1 = draw_point
                    xi1,yi1 = real_xy (imask.shape, wi, hi, xi1, yi1)
                    if point_save_mask :
                        last_imask = np.copy(imask) #save before first point draw
                        point_save_mask = False
                    imask = cv2.circle(imask, (xi1,yi1), linewidth, icolor,-1 ) 
                    iMainImageID = set_canvas_image (imask, igraph, iMainImageID, wi, hi)
                    window_interactive['-UNDOSTEP-'].update(disabled=False)
                elif values['-ILINE-'] and None not in (start_point, end_point):
                            prior_rect = igraph.draw_line(start_point, end_point, width=4, color = isel_color ) 
            elif event.endswith('+UP') and not (start_point is None):  # The drawing has ended because mouse up
                if values['-IFILL-']:
                    #fill by point
                    xi1,yi1 = start_point
                    xi1,yi1 = real_xy (imask.shape, wi, hi, xi1, yi1)
                    last_imask = np.copy(imask)
                    maskNone = np.zeros( (imask.shape[0]+2,imask.shape[1]+2), np.uint8)
                    _, imask, _, _  = cv2.floodFill(imask, maskNone, (xi1,yi1), icolor) 
                    iMainImageID = set_canvas_image (imask, igraph, iMainImageID, wi, hi)
                    window_interactive['-UNDOSTEP-'].update(disabled=False)
                if values['-IFILLQ-']:
                    #fill by point on quatized and get area
                    xi1,yi1 = start_point
                    xi1,yi1 = real_xy (imask.shape, wi, hi, xi1, yi1)
                    last_imask = np.copy(imask)
                    tmp_qimg = np.copy(iquantized)
                    maskNone = np.zeros( (imask.shape[0]+2,imask.shape[1]+2), np.uint8)
                    _, tmp_qimg, _, _  = cv2.floodFill(tmp_qimg, maskNone, (xi1,yi1), (0,255,0)) 
                    maskByContour = cv2.inRange(tmp_qimg, (0,254,0),(0,255,0))
                    imask[maskByContour == 255] = icolor[0]
                    iMainImageID = set_canvas_image (imask, igraph, iMainImageID, wi, hi)
                    window_interactive.refresh()
                    time.sleep(1)
                    iMainImageID = set_canvas_image (iquantized, igraph, iMainImageID, wi, hi)
                    window_interactive.refresh()
                    window_interactive['-UNDOSTEP-'].update(disabled=False)
                if values['-ILINE-'] and not end_point is None:
                    #line 
                    #linewidth = int(4*imask.shape[0]/wi)
                    linewidth=int(values["-IWIDTH-"])
                    igraph.delete_figure(prior_rect)
                    xi1,yi1 = start_point
                    xi2,yi2 = end_point
                    xi1,yi1 = real_xy (imask.shape, wi, hi, xi1, yi1)
                    xi2,yi2 = real_xy (imask.shape, wi, hi, xi2, yi2)
                    last_imask = np.copy(imask)
                    imask = cv2.line(imask, (xi1,yi1), (xi2,yi2), icolor, linewidth) 
                    iMainImageID = set_canvas_image (imask, igraph, iMainImageID, wi, hi)
                    window_interactive['-UNDOSTEP-'].update(disabled=False)
                # if values['-IPOINT-']:

                start_point, end_point = None, None  # enable grabbing a new rect
                dragging = False
                prior_rect = None
            
            if  event == 'Do grabcut' or values['-AUTO GRABCUT-'] :
                    if not values['-AUTO GRABCUT-']:
                        last_imask = np.copy(imask)
                        window_interactive['-UNDOSTEP-'].update(disabled=False)
                    if (255 in imask) and (128 in imask) and (0 in imask):
                        imask,iresultimg = grabcut_onbwgray(iimg, imask)
                        window_interactive['-IINFO-'].update( 'grabcut ok' )
                    else:
                        window_interactive['-IINFO-'].update( 'Need foreground, background and guess gray area' )
                    iMainImageID = set_canvas_image (imask, igraph, iMainImageID, wi, hi)
            if  event == 'Simple mask' :
                    last_imask = np.copy(imask)
                    window_interactive['-UNDOSTEP-'].update(disabled=False)
                    imask_inv = cv2.bitwise_not (imask)
                    imask_inv [imask_inv < 255] = 0
                    iresultimg = cv2.bitwise_and( iimg, iimg, mask = imask_inv )
                    if maskimg_mode == '-IIMGRESULT-':
                        iMainImageID = set_canvas_image (iresultimg, igraph, iMainImageID, wi, hi)
                    window_interactive['-IINFO-'].update( 'mask ok' )

            if (event == '-IFILLQ-') or (event == '-IQCOLORS-' and values['-IFILLQ-'])  :
                iquantized = quantize(iimg, K=int(values['-IQCOLORS-']))
                iMainImageID = set_canvas_image (iquantized, igraph, iMainImageID, wi, hi)
            elif (event == '-IMASK-') or (
                    maskimg_mode == '-IMASK-' 
                    and (event == 'Do grabcut' or event.endswith('+UP') and not values['-IFILLQ-'])
                    ):
                iMainImageID = set_canvas_image (imask, igraph, iMainImageID, wi, hi)
                maskimg_mode = '-IMASK-'
            elif event == '-IMASKIMG-'  or (
                    maskimg_mode == '-IMASKIMG-' 
                    and (event == 'Do grabcut' or event.endswith('+UP') and not values['-IFILLQ-'])
                    ):
                tmpimg = cv2.bitwise_and( iimg, iimg, mask = imask )
                iMainImageID = set_canvas_image (tmpimg, igraph, iMainImageID, wi, hi)
                maskimg_mode = '-IMASKIMG-'
            elif event == '-IIMG-'  or (
                    maskimg_mode == '-IIMG-' 
                    and (event == 'Do grabcut' or event.endswith('+UP') and not values['-IFILLQ-'])
                    ):
                iMainImageID = set_canvas_image (iimg, igraph, iMainImageID, wi, hi)
                maskimg_mode = '-IIMG-'
            elif ( (event == '-IIMGRESULT-') or (
                    maskimg_mode == '-IIMGRESULT-' 
                    and (event == 'Do grabcut' or event.endswith('+UP') and not values['-IFILLQ-'])
                    ) ) and not iresultimg is None :
                iMainImageID = set_canvas_image (iresultimg, igraph, iMainImageID, wi, hi)
                maskimg_mode = '-IIMGRESULT-'

        #---- end interactive -----


        #---- main window -----
        if window == window2:
            drawing_setting = values
        if window != window_interactive:

            if event == 'Save' and not (imgnew is None) :
                #fileout = os.path.join(values['-FOLDER OUT-'], values['-FILELIST-'][0] ) opecv cyrillic error
                fileout = values['-FILELIST-'][0]
                folder = values['-FOLDER OUT-']
                file_chosen, img, next_one_selected = saveFile (imgnew, fileout, folder, lb, window, graph)
            if event == 'Manual' and not (imgnew is None) :
                fileout = values['-FILELIST-'][0]
                folder = values['-FOLDER-']
                folder_out = values['-FOLDER OUT-']
                folder_out_manual = folder_out +"manual/"
                copyfile (folder + fileout, folder_out_manual + fileout)

            if event == '-FOLDER-' :                         # Folder name was filled in, make a list of files in the folder
                change_folder(window2)
            if event == '-FILELIST-' or next_one_selected == True:    # A file was chosen from the listbox
                file_chosen,img = change_file (window2, graph)
                if img.shape[0]>3000 : #alloc memory error if big image
                    (wnew, hnew, aspect) = ResizeWithAspectRatio (img.shape, 2000, 3000)
                    img = cv2.resize(img, (wnew, hnew) )
                next_one_selected = False
                #init interactive_mask_add with value = 200 <> 0 <> 128 <> 255 (0,128,255 - all used in mask)
                interactive_mask_add = np.full(img.shape[:2], 200, np.uint8) 

            if event == 'Show image':
                if mainImageID:
                    mainImageID = set_canvas_image (img, graph, mainImageID, w, h)
            if event == 'end image':
                if not (imgnew is None):
                    mainImageID = set_canvas_image (imgnew, graph, mainImageID, w, h)
            if event == 'Show mask':
                if mainImageID:
                    mainImageID = set_canvas_image (readymask, graph, mainImageID, w, h)
            if event == 'end mask':
                if not (resultmask is None):
                    mainImageID = set_canvas_image (resultmask, graph, mainImageID, w, h)

            if event == 'Mass format':
                imgnew = None
                threshold_only = True
                forest_only = False
                no_show = True
                last_processed_mode = 'bright'
                folderin = values['-FOLDER-']
                folderout = values['-FOLDER OUT-']
                script_path = os.getcwd()
                a_bar.update(100)
                b_bar.update(100)
                for i in range ( lb.size() ) :   # 0 .. lb.size()
                    filename = lb.get(i)
                    os.chdir(folderin)
                    img = cv2.imread(filename)
                    os.chdir(script_path)
                    if img is None :
                        print ("error happened on read file: ", filename)
                        exit(0)
                    window2['-FILENAME-'].update( filename )
                    frame, mainImageID, w, h,_ = apply_part1 (img, drawing_setting, graph, mainImageID, threshold_only, forest_only, a_bar, b_bar, no_show = True)
                    window2.read(timeout = 10)
                    window2.refresh()
                    imgnew,_ = apply_part2(img, drawing_setting, graph, w, h, windowTitle, only_bright = True, no_show = True)
                    os.chdir(folderout)
                    cv2.imwrite( filename.replace('.JPG', '.jpg'), imgnew )
                    os.chdir(script_path)

            if (event == 'Mask2Gimp' or 
                event == 'Gray remove' or 
                # event == 'Gray grabcut' or 
                event == 'Forest' or 
                event == 'Bright only' or 
                file_chosen) and not (img is None):

                imgnew = None
                no_show = False
                if event == 'Mask2Gimp':
                    save_mask = True
                else :
                    save_mask = False
                
                #for events
                if event == 'Gray remove':
                    last_processed_mode = 'dark'
                # if event == 'Gray grabcut':
                #     last_processed_mode = 'white'
                if event == 'Forest':
                    last_processed_mode = 'forest'
                if event == 'Bright only':
                    last_processed_mode = 'bright'
                
                grabcut = False
                #for mask2Gimp and new file
                if last_processed_mode == 'dark':
                    threshold_only = True
                    only_bright = False
                    forest_only = False
                    if not file_chosen and drawing_setting['-GRABCUT-']:
                        grabcut = True
                # elif last_processed_mode == 'white':
                #     forest_only = False
                #     threshold_only = True

                #     # threshold_only = False
                #     only_bright = False
                elif last_processed_mode == 'forest':
                    threshold_only = False
                    only_bright = False
                    forest_only = True
                    if not file_chosen and drawing_setting['-GRABCUT-']:
                        grabcut = True
                elif last_processed_mode == 'bright':
                    forest_only = False
                    threshold_only = True
                    only_bright = True

                frame, mainImageID, w, h, readymask = apply_part1 (img, drawing_setting, graph, mainImageID, threshold_only, forest_only, a_bar, b_bar, no_show)
                window2.read(timeout = 10)
                window2.refresh()
                imgnew, resultmask = apply_part2(img, drawing_setting, graph, w, h, windowTitle, only_bright, no_show, save_mask, readymask, grabcut, interactive_mask_add)
                firstrun = False
                file_chosen = False

                if event == 'Mask2Gimp':
                    fileout = values['-FILELIST-'][0]
                    folderin = values['-FOLDER-'] 
                    folderout = values['-FOLDER OUT-']

                        #run(src_filepath, mask_filepath, out_filepath)
                        #doble quotes -do not use in gimp
                    #run gimp an insert mask (in script)
                    #srcfile = "'" + folderin + fileout + "'"
                    srcfile =   "'" + os.getcwd() + "\\tmpimage.png" + "'"
                    maskfile =   "'" + os.getcwd() + "\\tmpmask.png" + "'"
                    outfile = "'" + folderout + fileout + ".xcf'"
                    arg_string = srcfile + "," + maskfile + "," + outfile
                    bat_file = '"' + os.getcwd() + "\\run-gimp.bat" + '" ' 
                    run_string = bat_file + '"' + arg_string + '"'  
                    run_string = run_string.replace("\\\\","\\")
                    run_string = run_string.replace("\\","/")
                    subprocess.run (run_string) 
                    #run gimp for editing
                    outfile = folderout + fileout + ".xcf"
                    bat_file = '"' + os.getcwd() + "\\run-gimp2.bat" + '" ' 
                    run_string = bat_file   
                    run_string = run_string.replace("\\\\","\\")
                    run_string = run_string.replace("\\","/")
                    outfile = outfile.replace("\\\\","\\")
                    outfile = outfile.replace("/","\\")
                    run_string += '"' + outfile + '"'
                    subprocess.run (run_string) 
                


            if event in ('-MOVE-', '-MOVEALL-'):
                # graph.Widget.config(cursor='fleur')
                graph.set_cursor(cursor='fleur')          # not yet released method... coming soon!
            elif not event.startswith('-GRAPH-'):
                graph.set_cursor(cursor='left_ptr')       # not yet released method... coming soon!
                # graph.Widget.config(cursor='left_ptr')
            if event in ('-WHITE-'):
                sel_color = 'white'
                fill_color = sel_color
            if event in ('-BLACK-'):
                sel_color = 'black'
                fill_color = sel_color
            if event in ('-RED-'):
                sel_color = 'red'
                fill_color = sel_color
            if event in ('-BLUE-'):
                sel_color = 'blue'
                fill_color = sel_color
            if event in ('-GREEN-'):
                sel_color = 'green'
                fill_color = ''

            if event == "-GRAPH-":  # if there's a "Graph" event, then it's a mouse
                x, y = values["-GRAPH-"]
                if (drawing_setting['-INFO-']) and not (img is None):
                    realx,realy = real_xy (img.shape, w, h, x, y)
                    pixbright = img[realy,realx]
                    alpha = drawing_setting['-ALPHA-'] / 100
                    beta = drawing_setting['-BETA-'] - 100
                    pixbright = cv2.convertScaleAbs(pixbright, alpha=alpha, beta=beta)
                    print ("pixel at: ", realx, realy , " bgr: ", pixbright[0], pixbright[1], pixbright[2])
                if not dragging:
                    start_point = (x, y)
                    dragging = True
                    drag_figures = graph.get_figures_at_location((x,y))
                    lastxy = x, y
                else:
                    end_point = (x, y)
                if prior_rect:
                    graph.delete_figure(prior_rect)
                delta_x, delta_y = x - lastxy[0], y - lastxy[1]
                lastxy = x,y
                if None not in (start_point, end_point) or drawing_setting['-ERASE-'] or drawing_setting['-CLEAR-']:
                    # if drawing_setting['-WHITE-']:
                    #     sel_color = 'white'
                    # if drawing_setting['-BLACK-']:
                    #     sel_color = 'black'
                    if drawing_setting['-EDIT INTERACTIVE-']:
                        prior_rect = graph.draw_rectangle(start_point, end_point,fill_color='', line_color='orange')
                    if drawing_setting['-RECT-']:
                        prior_rect = graph.draw_rectangle(start_point, end_point,fill_color=fill_color, line_color=sel_color)
                    if drawing_setting['-CIRCLE-']:
                        prior_rect = graph.draw_circle(start_point, end_point[0]-start_point[0], fill_color=fill_color, line_color=sel_color)
                    elif drawing_setting['-LINE-']:
                        prior_rect = graph.draw_line(start_point, end_point, width=4, color = sel_color ) 
                    # elif drawing_setting['-MOVE-']:
                    #     for fig in drag_figures:
                    #         graph.move_figure(fig, delta_x, delta_y)
                    #         graph.update()
                    elif drawing_setting['-POINT-']:
                        graph.draw_point((x,y), size=8, color = sel_color)
                    elif drawing_setting['-ERASE-']:
                        for figure in drag_figures:
                            if figure != mainImageID :
                                graph.delete_figure(figure)
                    elif drawing_setting['-CLEAR-']:
                        graph.erase()
                    # elif drawing_setting['-MOVEALL-']:
                    #     graph.move(delta_x, delta_y)
                    # elif drawing_setting['-FRONT-']:
                    #     for fig in drag_figures:
                    #         graph.bring_figure_to_front(fig)
                    # elif drawing_setting['-BACK-']:
                    #     for fig in drag_figures:
                    #         graph.send_figure_to_back(fig)
            elif event.endswith('+UP'):  # The drawing has ended because mouse up
                info = window["info"]
                info.update(value=f"grabbed rectangle from {start_point} to {end_point}")
                
                if drawing_setting['-EDIT INTERACTIVE-'] :
                    graph.delete_figure(prior_rect)
                    if not(readymask is None) :
                        xint1,yint1 = start_point
                        xint2,yint2 = end_point
                        xint1,yint1 = real_xy (img.shape, w, h, xint1, yint1)
                        xint2,yint2 = real_xy (img.shape, w, h, xint2, yint2)
                        if xint1 > xint2 :
                            xint1, xint2 = xint2, xint1
                        if yint1 > yint2 :
                            yint1, yint2 = yint2, yint1
                        imask = readymask[yint1:yint2,xint1:xint2]
                        imask[ imask == 255] = 128 #PB_FGD
                        imask_reset = np.copy(imask)
                        iimg = img[yint1:yint2,xint1:xint2]
                        iresultimg = None
                        window_interactive, iMainImageID, wi, hi = open_interactive(imask)
                        igraph = window_interactive['-IGRAPH-']
                        maskimg_mode  = '-IMASK-'
                        

                start_point, end_point = None, None  # enable grabbing a new rect
                dragging = False
                prior_rect = None
        #---- main window end ----
    window.close()
#end main

#--------------------------- run main procedure ------------------
main()