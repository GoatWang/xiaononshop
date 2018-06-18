def get_order_date_reply_messages(event):
    maximum_futere_days_for_ordering = 14
    available_dates = sorted(list(set(Bento.objects.filter(date__gt=datetime.now().date(), ready=True).values_list('date', flat=True))))[:maximum_futere_days_for_ordering]
    available_dates_len = len(available_dates)
    
    messages_count = available_dates_len // 4
    messages_count = messages_count + 1 if available_dates_len%4 != 0 else messages_count

    messages_with_btns = []
    for i in range(available_dates_len):
        messages_with_btns.append(available_dates[i*4:(i+1)*4].copy())

    messages = []
    for message_with_btns in messages_with_btns:
        actions = []
        for btn in message_with_btns:
            actions.append(
                    PostbackTemplateAction(
                            label=str(btn),
                            data= 'action=get_order_date_reply_messages&date='+str(btn)
                        )
                    )
        
        buttons_template_message = TemplateSendMessage(
                alt_text='訂餐日期選擇',
                template=ButtonsTemplate(
                    title='訂餐日期選擇',
                    text='請問哪一天想吃小農飯盒呢?',
                    actions=actions
                )
            )

        messages.append(buttons_template_message)
    return messages
